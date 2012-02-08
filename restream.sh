killall -9 ezstream
killall -9 ffmpeg
ffmpeg -i http://pawlacz.tk:8000/stream.ogg -f mp3 -b 64k -ac 2 -y pipe1.mp3 & ezstream -c ezstream_reencode_mp3.xml &
