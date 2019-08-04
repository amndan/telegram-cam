#!/usr/bin/env python2

import picamera
import time
import os
import cv2
from telegram.ext import Updater
from telegram.ext import CommandHandler
from picamera.array import PiRGBArray
import threading

class MovementExtractor():
    def __init__(self):
        self._lastImage = None
        self.moving = False

    def update(self, image):
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        image = cv2.GaussianBlur(image, (5, 5), 0)
        if(self._lastImage == None):
            self._lastImage = image
            self._moving = False
            return self._moving
        diff = cv2.absdiff(image, self._lastImage)
        diff = cv2.GaussianBlur(diff, (5, 5), 0)
        diff = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)[1]

        if(diff.sum() > 0):
            self._moving = True
        else:
            self._moving = False

        self._lastImage = image

        return self._moving

class MovementFilter():
    def __init__(self, thresh = 5):
        self._frameCountStill = 0
        self._thresholdStill = thresh
        self._moving = False

    def update(self, moving):
        if(moving == True):
            self._moving = moving
        else:
            if(self._moving):
                self._frameCountStill += 1
                if(self._frameCountStill >= self._thresholdStill):
                    self._moving = False
                    self._frameCountStill = 0
        return self._moving

def movement(filterr, extractor, camera):
    image = camera.captureStillImage()
    return filterr.update(extractor.update(image))
        
def cmdStart(bot, update):
    global g_active
    global g_lastChatId
    print('got /start...')
    g_lastChatId = update.message.chat_id
    g_active = not g_active
    if(g_active):
        bot.send_message(chat_id=update.message.chat_id, text='Recorder is active!')
    else:
        bot.send_message(chat_id=update.message.chat_id, text='Recorder is inactive!')

def cmdImage(bot, update):
    global g_cam
    print(threading.current_thread())
    print('capture image...')
    image = g_cam.captureStillImage()
    cv2.imwrite('/tmp/piCamImage.png', image)
    print('save cv image')
    print('send image...')
    bot.send_photo(chat_id=update.message.chat_id, photo=open('/tmp/piCamImage.png', 'rb'))
    print('ready')

def cmdVideo(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text='video cmd is not active')
    #bot.send_message(chat_id=update.message.chat_id, text='recording...')
    print('capture video...')
    #camera.start_recording('/tmp/my_video.h264')
    #camera.wait_recording(10)
    #camera.stop_recording()
    #os.system('rm /tmp/my_video.mp4')
    #os.system('MP4Box -add /tmp/my_video.h264:fps=10 -new  /tmp/my_video.mp4')
    print('send video...')
    #bot.send_message(chat_id=update.message.chat_id, text='sending...')
    #bot.send_video(chat_id=update.message.chat_id, video=open('/tmp/my_video.mp4', 'rb'))
    print('ready')

def cmdReboot(bot, update): 
    bot.send_message(chat_id=update.message.chat_id, text='Reboot...')
    os.system('reboot')

def cmdShutdown(bot, update):
    bot.send_message(chat_id=update.message.chat_id, text='Schutdown cmd is not active')

class Camera():
    def __init__(self):
        self._lock = threading.Lock()
        self._camera = picamera.PiCamera()
        self._ringbuffer = picamera.PiCameraCircularIO(self._camera, size=400000) # ca- 10.000 bytes / image --> 10 fps --> 4 seconds
        self._camera.framerate = 10
        self._camera.exposure_compensation = 25
        self._camera.ISO = 800
        time.sleep(1)
        self._camera.start_recording(self._ringbuffer,  format='h264')

    def startRecordingToRinguffer(self):
        self._lock.acquire()
        self._camera.split_recording(self._ringbuffer)
        self._lock.release()

    def captureStillImage(self):
        self._lock.acquire()
        rawCapture = PiRGBArray(self._camera)
        self._camera.capture(rawCapture, format='bgr', use_video_port=True)
        self._lock.release()
        return rawCapture.array

    def startRecordingToFile(self):
        self._lock.acquire()
        self._camera.split_recording('/tmp/after.h264')
        self._lock.release()

    def dumpRingbuffer(self):
        self._ringbuffer.copy_to('/tmp/before.h264')
        self._ringbuffer.clear()

def processRecordings(bot):
    os.system('MP4Box -cat /tmp/before.h264:fps=10 -cat /tmp/after.h264:fps=10 -new /tmp/my_video.mp4')

    if( not os.path.isfile('/tmp/my_video.mp4') ):
        bot.send_message(chat_id=g_lastChatId, text='try recover from no H264 error...')
        os.system('MP4Box -add /tmp/after.h264:fps=10 -new /tmp/my_video.mp4')

    if( not os.path.isfile('/tmp/my_video.mp4') ):
        bot.send_message(chat_id=g_lastChatId, text='error creating video')

    os.system('rm /tmp/before.h264 /tmp/after.h264')
    
def sendRecording(bot):
    global g_lastChatId
    if( not os.path.isfile('/tmp/my_video.mp4') ):
        bot.send_message(chat_id=g_lastChatId, text='error sending video :-(')
        return
    
    bot.send_message(chat_id=g_lastChatId, text='sending video...')
    
    try:
        bot.send_video(chat_id=g_lastChatId, video=open('/tmp/my_video.mp4', 'rb'))
    except:
        bot.send_message(chat_id=g_lastChatId, text='exception at sending video')

    os.system('rm /tmp/my_video.mp4')

g_cam = Camera()
g_active = False
g_lastChatId = None

def main():
    print('start app')

    global g_cam
    global g_active

    # todo: read token from protected file on disc to not depend on src
    updater = Updater(token='need-to-set-token-here')
    print(updater)
    dispatcher = updater.dispatcher

    start_handler = CommandHandler('start', cmdStart)
    dispatcher.add_handler(start_handler)

    image_handler = CommandHandler('image', cmdImage)
    dispatcher.add_handler(image_handler)

    video_handler = CommandHandler('video', cmdVideo)
    dispatcher.add_handler(video_handler)

    reboot_handler = CommandHandler('reboot', cmdReboot)
    dispatcher.add_handler(reboot_handler)
    
    shutdown_handler = CommandHandler('shutdown', cmdShutdown)
    dispatcher.add_handler(shutdown_handler)
    
    updater.start_polling()

    mf = MovementFilter()
    me = MovementExtractor()

    # todo: use python logging
    print('enter while')

    while(True):
        time.sleep(0.5)
        movement(mf, me, g_cam)
        if(not g_active):
            continue
        if(mf._moving):
            print('moving started')
            g_cam.startRecordingToFile()
            g_cam.dumpRingbuffer()

            startRec = time.time()
            while(True):
                time.sleep(0.5)
                condition1 = movement(mf, me, g_cam)
                condition2 = time.time() - startRec < 100
                if(not condition2):
                    # todo: need a force no movement method for movement filter in case of aborting recording
                    # if not there will be at least one more video recorded in next iteration due to filter behavior
                    g_active = False # prevent from endless recording
                    print('prevent from endless recording')
                    break
                if(not condition1):
                    break
            
            print('moving end')
            g_cam.startRecordingToRinguffer()
            processRecordings(updater.bot)
            sendRecording(updater.bot)
            print('exit inner while loop')
            
if __name__ == "__main__": 
    main()
