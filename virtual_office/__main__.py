#!/usr/bin/env python
# -*- coding: utf-8 -*-

from binascii import hexlify
from subprocess import Popen, PIPE
import click
import cv2
import fcntl
import numpy as np
import pprint
import sys
import v4l2

hsvLower =  np.array([55, 50, 80])
hsvUpper =  np.array([90, 190, 255])

@click.command()
@click.argument('bg')
def main(bg):
    print("OpenCV:", cv2.__version__)
    cameraCap = cv2.VideoCapture(-1)
    cameraCap.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
    cameraCap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cameraFPS = cameraCap.get(cv2.CAP_PROP_FPS)
    print("cameraFPS:", cameraFPS)

    dummyCamera = DummyCamera(None)

    videoCap = None
    if bg.lower().endswith('.mp4'):
        # background movie mode
        videoCap = cv2.VideoCapture(bg)
        videoFPS = videoCap.get(cv2.CAP_PROP_FPS)
        print("videoFPS:", videoFPS)
        videoFrameCount = videoCap.get(cv2.CAP_PROP_FRAME_COUNT)
        print("videoFrameCount:", videoFrameCount)
        skipFrame = int(videoFPS / cameraFPS) * 2
        print("skipFrame:", skipFrame)
        framePos = 0
    else:
        # background image mode
        bgImage = cv2.imread(bg)

    while True:
        k = cv2.waitKey(1)
        if k == 27:
            break

        if videoCap:
            videoCap.set(1, framePos)
            ret, videoFrame = videoCap.read()
            framePos += skipFrame
            if framePos >= videoFrameCount:
                framePos = 0
        else:
            videoFrame = bgImage.copy()

        ret, cameraFrame = cameraCap.read()
        videoShape = videoFrame.shape
        cameraShape = cameraFrame.shape
        roiWidth, roiHeight = cameraShape[:2]
        roi = videoFrame[0:roiWidth, 0:roiHeight]
        videoMask = makeMask(cameraFrame)
        cv2.imshow("videoMask", videoMask)
        maskedRoi = np.uint8(roi * (videoMask / 255.0))
        cv2.imshow('maskedRoi', maskedRoi)
        cameraMask = 1 - (videoMask / 255.0)
        #cv2.imshow("cameraMask", cameraMask)
        maskedCamera = np.uint8(cameraFrame * cameraMask)
        cv2.imshow('maskedCamera', maskedCamera)
        #cv2.imshow('maskedCamera', maskedCamera)
        blend = cv2.add(maskedRoi, maskedCamera)
        videoFrame[0:cameraShape[0], 0:cameraShape[1]] = blend
        cv2.imshow('result', videoFrame)
        dummyCamera.write(videoFrame)
    cameraCap.release()
    dummyCamera.release()
    cv2.destroyAllWindows()

def pick_color(event, x, y, flags, param):
    if event != cv2.EVENT_LBUTTONDOWN:
        return
    h, s, v = param[y, x]
    print("H: {}, S: {}, V: {}".format(h, s, v))

def removeNoise(hsvMask):
    debugFrame = cv2.cvtColor(hsvMask, cv2.COLOR_GRAY2BGR)
    # remove noise in foreground
    contours, _ = cv2.findContours(hsvMask,
                                   cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    #debugFrame = cv2.drawContours(debugFrame, contours, -1, (0,255,0), 2)
    contours = list(filter(lambda c: cv2.contourArea(c) < 500, contours))
    for c in contours:
        cv2.fillConvexPoly(hsvMask, c, 0)

    # remove noise in background
    contours, _ = cv2.findContours(cv2.bitwise_not(hsvMask),
                                   cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    debugFrame = cv2.drawContours(debugFrame, contours, -1, (0,0,255), 2)
    contours = list(filter(lambda c: cv2.contourArea(c) < 5000, contours))
    debugFrame = cv2.drawContours(debugFrame, contours, -1, (0,255,0), 2)
    for c in contours:
        cv2.fillConvexPoly(hsvMask, c, 255)
    videoMask = cv2.cvtColor(hsvMask, cv2.COLOR_GRAY2BGR)
    cv2.imshow("remove noise", debugFrame)


def makeMask(cameraFrame):
    hsv = cv2.cvtColor(cameraFrame, cv2.COLOR_BGR2HSV)

    cv2.namedWindow('raw')
    cv2.setMouseCallback('raw', pick_color, hsv)
    cv2.imshow('raw', cameraFrame)

    hsvMask = cv2.inRange(hsv, hsvLower, hsvUpper)
    cv2.namedWindow('hsvMask')
    cv2.setMouseCallback('hsvMask', pick_color, cameraFrame)
    cv2.imshow("hsvMask", hsvMask)
    hsvMask = cv2.medianBlur(hsvMask, 3)
    cv2.imshow("hsvMask1", hsvMask)
    removeNoise(hsvMask)
    cv2.imshow("hsvMask2", hsvMask)

    #hsvMask = cv2.dilate(hsvMask, None, iterations=1)
    #hsvMask = cv2.erode(hsvMask, None, iterations=1)
    #cv2.imshow("hsvMask2", hsvMask)
    hsvMask = cv2.GaussianBlur(hsvMask, (11, 11), 0)
    #cv2.imshow("mask", mask)
    #cv2.imshow("hsvMask3", hsvMask)
    videoMask = cv2.cvtColor(hsvMask, cv2.COLOR_GRAY2BGR)
    return videoMask

# convert BGR to YUYV442
def bgr2yuyv422(bgr):
    yuv = cv2.cvtColor(bgr, cv2.COLOR_BGR2YUV)
    height, width, _ = yuv.shape
    bytesperline = width * 2
    sizeimage = bytesperline * height
    out = np.zeros((height, int(width / 2), 4), dtype=np.uint8)
    yuvPair = yuv.ravel().reshape(height, int(width / 2), 6)
    # Y0
    out[:,:,0] = yuvPair[:,:,0]
    # U = (U0 + U1) / 2
    out[:,:,1] = yuvPair[:,:,1] / 2 + yuvPair[:,:,4] / 2
    # Y1
    out[:,:,2] = yuvPair[:,:,3]
    # V = (V0 + V1) / 2
    out[:,:,3] = yuvPair[:,:,2] / 2 + yuvPair[:,:,5] / 2
    return out

class DummyCamera():
    camera = None

    def findDummyCamera(self):
        for i in range(10):
            try:
                fd = open('/dev/video{}'.format(i), 'wb')
                cp = v4l2.v4l2_capability()
                fcntl.ioctl(fd, v4l2.VIDIOC_QUERYCAP, cp)
                if cp.driver.decode() == 'v4l2 loopback':
                    return fd
                fd.close()
            except:
                pass
        print('dummy camera notfound')
        return None

    def __init__(self, device):
        width = 1280
        height = 720
        if device:
            self.camera = open(device, 'wb')
        else:
            self.camera = self.findDummyCamera()
        if not self.camera:
            exit(1)
        fmt = v4l2.v4l2_format()
        fmt.type = v4l2.V4L2_BUF_TYPE_VIDEO_OUTPUT
        fmt.fmt.pix.pixelformat = v4l2.V4L2_PIX_FMT_YUYV
        fmt.fmt.pix.width = width
        fmt.fmt.pix.height = height
        fmt.fmt.pix.field = v4l2.V4L2_FIELD_NONE
        fmt.fmt.pix.bytesperline = width * 2
        fmt.fmt.pix.sizeimage = width * height * 2
        fmt.fmt.pix.colorspace = v4l2.V4L2_COLORSPACE_SRGB
        ret = fcntl.ioctl(self.camera, v4l2.VIDIOC_S_FMT, fmt)

    def release():
        self.camera.close()

    def write(self, frame):
        yuyv422 = bgr2yuyv422(frame)
        self.camera.write(yuyv422.tobytes())

class FFmpegDummyCamera():
    ffmpeg = None

    def __init__(self, device):
        self.ffmpeg = Popen(['ffmpeg', '-y', '-i', '-',
                             '-pix_fmt', 'yuyv422',
                             '-f', 'v4l2', device], stdin=PIPE)

    def write(self, frame):
        res, jpg = cv2.imencode('.jpg', frame)
        self.ffmpeg.stdin.write(jpg.tobytes())

if __name__ == '__main__':
    main()
