import argparse
import math
import cv2
import shutil
import time
import keyboard

import subprocess
import threading
import sys

import pyaudio
import wave

def rgbAnsiBg(r, g, b, txt):
    return f'\033[48;2;{r};{g};{b}m{txt}\033[0m'
def rgbAnsi(r, g, b, txt):
    return f'\033[38;2;{r};{g};{b}m{txt}\033[0m'

def frameToConsole(
        frame, width=30, height=30,
        addLinesToBack=0, # デバッグ用の文字を映像の後の行に追加する
        colorMode='color',
        fontColor=[255, 255, 255], # 完全な白だとコンソールソフト側で色が上書きされることがある
        renderMode='line'):
    height = height - addLinesToBack
    frame = cv2.resize(frame, (width, height))
    
    char = ' '

    print(f'\033[{height + addLinesToBack}A', end='') 
    if colorMode == 'color': 
        if renderMode == 'once':
            lines = ''
            for row in frame:
                line = ''.join(rgbAnsiBg(pixel[2], pixel[1], pixel[0], char) for pixel in row)
                lines += line + '\n'
            print(lines, end='')
        else: 
            for row in frame:
                line = ''.join(rgbAnsiBg(pixel[2], pixel[1], pixel[0], char) for pixel in row)
                print(line)
    else: 
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        chars = [
            ' ', '.', ':', '-', '=', '+', '*', 
            '░', '▒', '▓', '█'
        ]
        gray = (gray / 256 * len(chars))
        gray = gray.astype(int)
        
        if renderMode == 'once':
            lines = ''
            for row in gray:
                line = ''.join(chars[pixel] for pixel in row)
                if fontColor is not None:
                    line = rgbAnsi(fontColor[0], fontColor[1], fontColor[2], line)
                lines += line + '\n'
            print(lines, end='')
        else:
            for row in gray:
                line = ''.join(chars[pixel] for pixel in row)
                if fontColor is not None:
                    line = rgbAnsi(fontColor[0], fontColor[1], fontColor[2], line)
                print(line)

def consoleInit():
    consoleSize = shutil.get_terminal_size()
    print('\n' * (consoleSize.lines - 1))

def mathFloor(num, fNum):
    fNum = (10 ** fNum)
    return math.floor(num * fNum) / fNum

def play_audio():
        wf = wave.open("temp.wav", 'rb')
        p = pyaudio.PyAudio()

        # デフォルトのオーディオデバイスを使用
        stream = p.open(
            format=p.get_format_from_width(wf.getsampwidth()),
            channels=wf.getnchannels(),
            rate=wf.getframerate(),
            output=True
        )

        # 音声を再生する
        data = wf.readframes(1024)
        while len(data) > 0:
            stream.write(data)
            data = wf.readframes(1024)

def videoToConsole(videoPath, debug=False, playAudio=True, width=None, height=None, colorMode='color', fontColor=None, renderMode='line'):
    print('Loading Video File...')
    cap = cv2.VideoCapture(videoPath)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frameInterval = mathFloor(1 / fps, 5)

    videoWidth = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    videoHeight = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    aspectRatio = videoHeight / videoWidth

    fullSize = False
    if width is not None and height is None:
        height = int(width * aspectRatio)
    elif width is None and height is not None:
        width = int(height / aspectRatio)
    else:
        fullSize = True

    duration = 0
    fpsHistory = 0

    frameSkipDelay = 0

    # Play Sound
    if playAudio:
        print('Loading Sound File...')

    consoleInit()
    time.sleep(0.1)

    if playAudio:
        audio_thread = threading.Thread(target=play_audio)
        audio_thread.daemon = True
        audio_thread.start()
    
    videoStartTime = time.perf_counter()
    while cap.isOpened():
        checkQuit()
        colorMode = colorChange(colorMode)
        frameStartTime = time.perf_counter()
        ret, frame = cap.read()
        if not ret:
            break
        currentFrameNum = int(cap.get(cv2.CAP_PROP_POS_FRAMES))

        addLinesToBack = 0
        if debug:
            addLinesToBack = 7
        if fullSize:
            consoleSize = shutil.get_terminal_size()
            width = consoleSize.columns
            height = consoleSize.lines - 1
        frameToConsole(
            frame, width=width, height=height, addLinesToBack=addLinesToBack,
            colorMode=colorMode,
            fontColor=fontColor,
            renderMode=renderMode
        )
        renderEndTime = time.perf_counter()
        consoleRenderTime = renderEndTime - frameStartTime

        realTime = renderEndTime - videoStartTime
        frameDelayTime = realTime - duration
        
        if duration < realTime - frameInterval:
            duration += frameInterval
            skipSleepTime, skipFrameNum = math.modf((frameDelayTime + frameSkipDelay) / frameInterval)
            
            skipStartTime = time.perf_counter()
            for _ in range(int(skipFrameNum)):
                cap.grab()
                duration += frameInterval
            skipEndTime = time.perf_counter()
            frameSkipDelay = skipEndTime - skipStartTime

            while duration > realTime:
                realTime = time.perf_counter() - videoStartTime

        else:
            duration += frameInterval
            while duration > realTime:
                realTime = time.perf_counter() - videoStartTime

        if debug:
            endTime = time.perf_counter()
            fps = mathFloor(1 / (endTime - frameStartTime), 2)
            fpsHistory += fps
            print('-' * consoleSize.columns)
            print('FPSAve: ' + str(mathFloor(fpsHistory / currentFrameNum, 2)))
            print('FPS: ' + str(fps))
            print('Frame Interval: ' + str(frameInterval))
            print('console Render Time: ' + str(mathFloor(consoleRenderTime, 6)))
            print('Duration: ' + str(mathFloor(duration, 6)) + ' / RealTime' + str(mathFloor(realTime, 6)))
            print('-' * consoleSize.columns)
            
    cap.release()
    return 0

def checkQuit():
    if keyboard.is_pressed('q'):
        print('停止中...')
        exit()
    return

def colorChange(colorMode):
    if keyboard.is_modifier('c'):
        return 'color' if colorMode == 'mono' else 'mono'
    return colorMode

def ffmpeg(inputFile, outputFile):
    command = ['ffmpeg', '-y', '-i', inputFile, outputFile]
    subprocess.run(command, check=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Console Video Player')
    parser.add_argument('videoPath', type=str, help='再生するビデオファイルのpath')
    parser.add_argument('--loop', action='store_true', help='ループ再生')
    parser.add_argument('--width', type=int, help='幅')
    parser.add_argument('--height', type=int, help='高さ')
    parser.add_argument('--playAudio', action='store_true', help='Play audio along with video')
    parser.add_argument('--colorMode', type=str, choices=['mono', 'color'], default='mono', help='フルカラーかモノクロか')
    parser.add_argument('--fontColor', type=str, help='モノクロ時の文字色(例: 256,256,256)')
    parser.add_argument('--renderMode', type=str, choices=['once', 'line'], default='line', help='consoleへのテキストの描画方法')
    parser.add_argument('--debug', action='store_true', help='デバッグモード')
    args = parser.parse_args()

    videoPath = './video.webm'
    if args.videoPath is not None:
        videoPath = args.videoPath

    # Convert Audio File
    if args.playAudio:
        print('Converting Audio File...')
        ffmpeg(videoPath, './temp.wav')

    fontColor = None
    if args.fontColor is not None:
        fontColor = [int(c) for c in args.fontColor.split(',')]

    while True:
        videoToConsole(videoPath,
            debug=args.debug,
            playAudio=args.playAudio,
            width=args.width, height=args.height,
            colorMode=args.colorMode, fontColor=fontColor,
            renderMode=args.renderMode
        )
        if not args.loop:
            break
