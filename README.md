# Virtual Office

## 概要

実カメラと背景を合成して仮想カメラに出力します。

* 背景(画像・動画どちらでも)

<img src="bg.jpg" width="50%" />

* 物理カメラ

<img src="camera.png" width="50%" />

* 仮想カメラ出力

<img src="output.png" width="50%" />

## 準備

* 仮想カメラのセットアップ

~~~
$ sudo apt install v4l2loopback-dkms
$ sudo modprobe v4l2loopback exclusive_caps=1
~~~

* 依存ライブラリのインストール

~~~
$ poetry update
~~~

## 実行

実カメラ(/dev/video0)、仮想カメラ(/dev/video2)の場合はデバイスを自動検出します。

~~~
$ poetry run main bg.jpg
~~~

物理カメラが複数ある場合は指定`--camera`オプションで指定します。

~~~
$ poetry run main --camera=/dev/video2 bg.jpg
~~~

## Tips

* カメラをリスト

~~~
$ v4l2-ctl --list-devices
~~~

* カメラのフォーマットをリスト

~~~
$ v4l2-ctl -d /dev/video0 --list-formats-ext
~~~

* カメラの解像度を変更

~~~
$ v4l2-ctl -d /dev/video0 --set-fmt-video=width=1280,height=720 --set-parm=10
~~~
