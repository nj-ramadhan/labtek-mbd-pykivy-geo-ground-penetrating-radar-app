import serial, serial.tools.list_ports
import numpy as np
import json
import kivy
import sys
import os
from kivy.app import App
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.clock import Clock
from kivy.config import Config
from kivy.garden.matplotlib.backend_kivyagg import FigureCanvasKivyAgg
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.figure import Figure
import matplotlib.colors as mcolors
from matplotlib.colors import ListedColormap, LinearSegmentedColormap
import pyaudio
from datetime import datetime
from segpy.writer import write_segy

plt.style.use('bmh')
p = pyaudio.PyAudio()

SAMPLESIZE = 500 # number of data points to read at a time default 4096
SAMPLERATE = 100000 # time resolution of the recording self.device (Hz) 44100
TIMESAMPLE = 0.01 #in second
DISTANCE = 50

# stream=p.open(format=pyaudio.paFloat32,channels=1,rate=SAMPLERATE,input=True,frames_per_buffer=SAMPLESIZE)

Window.clearcolor = (.9, .9, .9, 1)
Window.fullscreen = 'auto'
# Window.fullscreen = True
# Window.size = (2880 , 1920)
kivy.require('2.1.0')

# Designate Our .kv design file 
kv = Builder.load_file('main.kv')
# Builder.load_file('main.kv')
#Define our different screens
class MainWindow(BoxLayout):
    checks_waveform = []
    checks_method = []
    flag_signal = False
    flag_graph = False
    flag_map = False
    flag_move = False

    dt_waveform = ""
    dt_method = ""
    lon = 107.6213
    lat = -6.8775
    zoom = 19
    dt_slider_distance = 0
    dt_distance = 0
    last_distance = 0
    dt_delay = 0
    dt_interval = 10
    min_graph = 0.00
    max_graph = 2.0

    data_signal = np.zeros(50)
    data_colormap = np.zeros((SAMPLESIZE, DISTANCE))
    data_adc = np.zeros(20)

    def __init__(self):
        super(MainWindow, self).__init__()

        self.fig1, self.ax = plt.subplots()
        # self.fig2, (self.ax1, self.ax2, self.ax3) = plt.subplots(nrows=1, ncols=3, gridspec_kw={'width_ratios': [10, 1, 1]})
        self.fig2, (self.ax1, self.ax2) = plt.subplots(nrows=1, ncols=2, gridspec_kw={'width_ratios': [10, 2]})
        self.ids.slider_distance.max = DISTANCE
        self.setting_screen()

    def hide_widget(self, wid, dohide=True):
        if hasattr(wid, 'saved_attrs'):
            if not dohide:
                wid.height, wid.size_hint_x,  wid.size_hint_y, wid.opacity, wid.disabled = wid.saved_attrs
                del wid.saved_attrs
        elif dohide:
            wid.saved_attrs = wid.height, wid.size_hint_x, wid.size_hint_y, wid.opacity, wid.disabled
            wid.height, wid.size_hint_x, wid.size_hint_y, wid.opacity, wid.disabled = 0, None, None, 0, True

    def setting_screen(self):
        # self.ids.layout_graph_carrier.add_widget(FigureCanvasKivyAgg(self.fig1))
        self.ids.layout_graph_signal.clear_widgets()

        self.hide_widget(self.ids.layout_setting, False)
        self.hide_widget(self.ids.layout_graph, True)
        self.hide_widget(self.ids.layout_map, True)

        self.ids.bt_screen_setting.disabled = True
        self.ids.bt_screen_graph.disabled = False
        self.ids.bt_screen_map.disabled = False

        self.ids.bt_update_graph.disabled = True
        self.ids.bt_save_data.disabled = True
        self.ids.bt_save_graph.disabled = True
        self.ids.bt_update_map.disabled = True

        self.ids.label_page.text = "SETTING SCREEN"
        Clock.unschedule(self.update_enco)
        Clock.unschedule(self.update_graph_odometry)
        Clock.unschedule(self.update_graph_time)

    def graph_screen(self):
        self.ids.layout_graph_carrier.clear_widgets()

        self.hide_widget(self.ids.layout_setting, True)
        self.hide_widget(self.ids.layout_graph, False)
        self.hide_widget(self.ids.layout_map, True)

        self.ids.bt_screen_setting.disabled = False
        self.ids.bt_screen_graph.disabled = True
        self.ids.bt_screen_map.disabled = False

        self.ids.bt_save_data.disabled = False
        self.ids.bt_save_graph.disabled = False
        self.ids.bt_update_map.disabled = True

        self.ids.label_page.text = "GRAPH SCREEN"

        if("ODOMETRY" in self.dt_method):
            self.ids.bt_update_graph.disabled = True
            Clock.schedule_interval(self.update_graph_odometry, 1)

        elif("CONTINUOUS" in self.dt_method):
            self.ids.bt_update_graph.disabled = True
            Clock.schedule_interval(self.update_graph_time, 2)

        elif("MANUAL" in self.dt_method):
            self.ids.bt_update_graph.disabled = False

        else:
            self.ids.bt_update_graph.disabled = False


    def map_screen(self):
        self.ids.layout_graph_carrier.clear_widgets()
        self.ids.layout_graph_signal.clear_widgets()

        self.hide_widget(self.ids.layout_setting, True)
        self.hide_widget(self.ids.layout_graph, True)
        self.hide_widget(self.ids.layout_map, False)

        self.ids.bt_screen_setting.disabled = False
        self.ids.bt_screen_graph.disabled = False
        self.ids.bt_screen_map.disabled = True

        self.ids.bt_update_graph.disabled = True
        self.ids.bt_save_data.disabled = True
        self.ids.bt_save_graph.disabled = True
        self.ids.bt_update_map.disabled = False

        self.ids.label_page.text = "MAP SCREEN"
        Clock.unschedule(self.update_enco)
        Clock.unschedule(self.update_graph_odometry)
        Clock.unschedule(self.update_graph_time)

    def refresh(self):
        ports = serial.tools.list_ports.comports()
        for port, desc, hwid in sorted(ports):
            print("{}: {} [{}]".format(port, desc, hwid))                
            self.com = str(port)
        try:
            self.ids.txt_com.text = self.com
            self.device = serial.Serial(port=self.com, baudrate=115200, timeout=.1)
            self.ids.bt_open_close_serial.disabled = False
            self.ids.txt_com.disabled = True
            self.ids.bt_refresh.disabled = True
            self.ids.bt_send_signal.disabled = False
            self.ids.bt_open_close_serial.text = "CLOSE COMMUNICATION"
            Clock.schedule_interval(self.update_data, 1)
            print("success open communication")
            self.ids.label_notif.text = "success open communication"
            self.ids.label_notif.color = 0,0,1
        except:
            print("error open communication")
            self.ids.label_notif.text = "error open communication"
            self.ids.label_notif.color = 1,0,0

    def update_data(self, interval):
        print("read")
        try:
            if self.device.in_waiting > 0:
                serialString = self.device.readline()
                # print(serialString)
                decodedSerialString = serialString.decode("utf-8")
                print(decodedSerialString)
            
                data_json = json.loads(decodedSerialString)
                print(data_json)

                if(data_json["type"] == "ENCO"):
                    print("get encoder")

                    self.dt_slider_distance = data_json["Pos"]
                    self.ids.slider_distance.value = float(self.dt_slider_distance / 1000)
                    self.dt_distance = int(self.dt_slider_distance / 1000)
                    
                    print("success update encoder data")
                    self.ids.label_notif.text = "success update encoder data"
                    self.ids.label_notif.color = 0,0,1
                    
                    print("last:"+str(self.last_distance)+" real:"+str(self.dt_distance))
                    if(self.last_distance!=self.dt_distance):
                        self.flag_move = True

                    self.last_distance = self.dt_distance


                elif(data_json["type"] == "GPS"):
                    print("get gps")

                    sign_ns = 1
                    sign_ew = 1
                    ns = data_json["ns"]
                    ew = data_json["ew"]

                    if(ns > 50):
                        sign_ns = -1
                    
                    if(ew > 100):
                        sign_ew = -1

                    self.lon = (data_json["long"] * sign_ew / 100) + 0.248
                    print(self.lon)
                    self.ids.txt_lon.text = str(format(self.lon, '.3f'))

                    self.lat = (data_json["lat"] * sign_ns / 100) - 0.35
                    print(self.lat)
                    self.ids.txt_lat.text = str(format(self.lat, '.3f'))

                    self.map_mark()

                    print("success update map data")
                    self.ids.label_notif.text = "success update map data"
                    self.ids.label_notif.color = 0,0,1
        except:
            print("error reading data")
            self.ids.label_notif.text = "error reading data"
            self.ids.label_notif.color = 1,0,0

    def update_graph_odometry(self, interval):
        Clock.schedule_interval(self.update_enco, 1)
        if(self.flag_move):
            self.update_graph()
            self.flag_move = False

    def update_graph_time(self, interval):
        self.update_graph()
        self.dt_slider_distance += 1000
        self.ids.slider_distance.value = float(self.dt_slider_distance / 1000)
        self.dt_distance = int(self.dt_slider_distance / 1000)
        
        

    def update_graph(self):
        stream = p.open(format=pyaudio.paFloat32,
                        channels = 1,
                        rate = SAMPLERATE,
                        frames_per_buffer = SAMPLESIZE,
                        input = True)
        
        x = np.linspace(0, SAMPLESIZE-1, SAMPLESIZE)
        # for i in range(0, int(SAMPLERATE / SAMPLESIZE * TIMESAMPLE)):self.dt_interval
        # for i in range(0, int(SAMPLERATE / SAMPLESIZE * self.dt_interval / 5)):

        for i in range(0, int(SAMPLERATE / SAMPLESIZE * TIMESAMPLE)):
            self.data_signal = np.frombuffer(stream.read(SAMPLESIZE), dtype=np.float32)
            # self.data_signal_stereo = np.frombuffer(stream.read(SAMPLESIZE), dtype=np.float32)
        # print(self.data_signal_stereo.shape)
        # temp_data_signal_stereo = self.data_signal_stereo
        # temp_data_signal_stereo.resize([SAMPLESIZE, 2])
        # print(temp_data_signal_stereo.shape)
        # self.data_signal = temp_data_signal_stereo[:, 0]
        # self.data_signal.flatten
        # self.data_signal_2 = temp_data_signal_stereo[:, 1]
        # print(self.data_signal.shape)
          
        x_spec = np.fft.fftfreq(SAMPLESIZE, d = 1.0 / SAMPLERATE)
        y_temp = np.fft.fft(-self.data_signal[0:SAMPLESIZE])
        y_spec = np.asarray([np.sqrt(c.real ** 2 + c.imag ** 2) for c in y_temp])

        self.dt_distance = int(self.dt_slider_distance / 1000)

        filtered_signal = self.data_signal.copy()
        filtered_signal[(filtered_signal > self.max_graph)] = self.max_graph
        
        #np.where(self.data_signal > 0.01, 0.0 ,self.data_signal)
        #np.where(self.data_signal < -0.01, 0.0 ,self.data_signal)
        # print(self.data_colormap.shape)
        #print(self.data_colormap)
        #print(self.data_signal)
        
        #self.data_signal = filtered_signal
        if(self.dt_distance >= DISTANCE):
            # temp_data_signal = self.data_signal
            temp_data_signal = y_spec
            temp_data_signal.resize([SAMPLESIZE, 1])
            self.data_colormap = np.concatenate([self.data_colormap, temp_data_signal], axis=1)
            #np.dstack((self.data_colormap, self.data_signal))
            self.ids.slider_distance.max += 1
            
        else:
            # self.data_colormap[: , self.dt_distance] = self.data_signal
            self.data_colormap[: , self.dt_distance] = y_spec

        stream.stop_stream()
        stream.close()

        self.fig2, (self.ax1, self.ax2) = plt.subplots(nrows=1, ncols=2, gridspec_kw={'width_ratios': [10, 1]})
        self.fig2.tight_layout()
        self.fig2.set_facecolor((.9,.9,.9))
       
        self.ax1.axis([0,DISTANCE, SAMPLESIZE/2,0])
        #self.ax1.axis([0,DISTANCE, SAMPLERATE/16,0])
        self.ax1.set_xlabel('distance (m)', fontsize=20)
        self.ax1.set_ylabel('depth (m)', fontsize=20)
        self.ax1.set_xlim(0, self.ids.slider_distance.max)
        self.ax1.grid(False)

        # cgrid = np.linspace(self.min_graph, self.min_graph, 10)
        # cmap, norm = mcolors.from_levels_and_colors(cgrid,['blue', 'green', 'yellow', 'red'])
        
        clrmesh = self.ax1.pcolor(self.data_colormap, cmap='turbo', vmin=self.min_graph, vmax=self.max_graph)
        # clrmesh = self.ax1.pcolor(self.data_colormap, cmap=cmap, norm=norm)
        self.fig2.colorbar(clrmesh, ax=self.ax1, format='%f')

        # self.ax2.axis([self.min_graph, self.max_graph, SAMPLESIZE-1, 0])
        # self.ax2.set_xlabel('amplitude (dB)', fontsize=25)
        # self.ax2.set_ylabel('frequency (Hz)', fontsize=25)
        # self.ax2.plot(self.data_signal, x, lw=1)

        self.ax2.axis([self.min_graph, self.max_graph, SAMPLERATE/2, 0])
        self.ax2.set_xlabel('amplitude', fontsize=20)
        self.ax2.set_ylabel('frequency (Hz)', fontsize=20)
        self.ax2.plot(y_spec, -x_spec, lw=1,marker= 'o', linestyle='-')

        self.ids.layout_graph_signal.clear_widgets()
        self.ids.layout_graph_signal.add_widget(FigureCanvasKivyAgg(self.fig2))

    def update_enco(self, interval):
        try:
            data_json = json.dumps({"type":"ENCO"})
            str_send = data_json + "\n"
            self.device.write(str_send.encode())        
            print(str_send)
        except:
            print("error updating encoder")
            self.ids.label_notif.text = "error updating encoder"
            self.ids.label_notif.color = 1,0,0

    def update_map(self, interval):
        try:
            data_json = json.dumps({"type":"GPS"})
            str_send = data_json + "\n"
            self.device.write(str_send.encode())        
            print(str_send)
        except:
            print("error updating map")
            self.ids.label_notif.text = "error updating map"
            self.ids.label_notif.color = 1,0,0
            

    def map_mark(self):
        self.lon = float(self.ids.txt_lon.text)
        self.lat = float(self.ids.txt_lat.text)
        self.zoom = int(self.ids.slider_zoom.value)

        self.ids.map_view.lon = self.lon
        self.ids.map_view.lat = self.lat
        self.ids.map_view.zoom = self.zoom

        self.ids.map_marker.lon = self.lon
        self.ids.map_marker.lat = self.lat

        print("long:" + str(self.lon) + ", lat:" + str(self.lat) + ", zoom:" + str(self.zoom))

    def open_close_serial(self):
        if (self.device.isOpen()):
            self.device.close()
            self.ids.txt_com.disabled = False
            self.ids.bt_refresh.disabled = False
            self.ids.bt_send_signal.disabled = True            
            self.ids.bt_open_close_serial.text = "OPEN COMMUNICATION"
            Clock.unschedule(self.update_data)
            print("communication port is closed")
            self.ids.label_notif.text = "communication port is closed"
            self.ids.label_notif.color = 0,0,1
        else:
            self.device.open()
            self.ids.txt_com.disabled = True
            self.ids.bt_refresh.disabled = True
            self.ids.bt_send_signal.disabled = False
            self.ids.bt_open_close_serial.text = "CLOSE COMMUNICATION"
            Clock.schedule_interval(self.update_data, 1)
            print("communication port is opened")
            self.ids.label_notif.text = "communication port is opened"
            self.ids.label_notif.color = 0,0,1
            
    def stop_signal(self):
        self.flag_signal = False
        self.ids.bt_send_signal.text = "GENERATE SIGNAL"

        data_json = json.dumps({"type":"STOP"})
        str_send = data_json + "\n"
        self.device.write(str_send.encode())
        print(str_send)            

        print("signal stopped")
        self.ids.label_notif.text = "signal stopped"
        self.ids.label_notif.color = 1,0,0

    def send_signal(self):
        self.dt_frequency_min = self.ids.slider_min.value
        self.dt_frequency_max = self.ids.slider_max.value
        self.dt_interval = self.ids.slider_interval.value

        offset = (self.dt_frequency_max + self.dt_frequency_min) / 2
        amplitude = (self.dt_frequency_max - self.dt_frequency_min) / 2

        x_axis = np.linspace(0, 100, int(10000/self.dt_interval), endpoint=True) #20 data per periode in 100ms axis

        if("TRIANGLE" in self.dt_waveform):
            y_axis = offset + (4 * amplitude / self.dt_interval) * np.abs((((x_axis - self.dt_interval / 4) % self.dt_interval) + self.dt_interval) % self.dt_interval - self.dt_interval / 2 ) - amplitude
            data_adc = np.round(0.0 + (1.0 - 0.0) * ((y_axis - 160) / (360 - 160)) , 2)
            # print(y_axis)
        elif("SQUARE" in self.dt_waveform):
            y_axis = offset + (amplitude * np.sign (np.sin(2 * np.pi * 1 / self.dt_interval * x_axis)))
            data_adc = np.round(0.0 + (1.0 - 0.0) * ((y_axis - 160) / (360 - 160)) , 2)
            # print(y_axis)
        elif("SAWTOOTH" in self.dt_waveform):
            y_axis = self.dt_frequency_min + ((2 * amplitude / self.dt_interval) * (x_axis % self.dt_interval))
            data_adc = np.round(0.0 + (1.0 - 0.0) * ((y_axis - 160) / (360 - 160)) , 2)
            # print(y_axis)
        else:
            y_axis = 0 * x_axis
            data_adc = y_axis

        if(self.flag_signal):
            y_axis = 0 * x_axis
            self.stop_signal()

        else:
            self.flag_signal = True
            self.ids.bt_send_signal.text = "STOP SIGNAL"
            try:
                data_json = json.dumps({"type":"DAC","value":list(data_adc[0:99:5]),"periode":self.dt_interval})
                str_send = data_json + "\n"
                self.device.write(str_send.encode())
                print(str_send)

                print("success generating signal")
                self.ids.label_notif.text = "success generating signal"
                self.ids.label_notif.color = 0,0,1
            except:
                print("error generating signal")
                self.ids.label_notif.text = "error generating signal"
                self.ids.label_notif.color = 1,0,0

        self.fig1, self.ax = plt.subplots()
        self.fig1.tight_layout()
        self.fig1.set_facecolor((.9,.9,.9))
        self.ax.set_facecolor((.9,.9,.9))
        self.ax.set_xlabel('time (ms)', fontsize=25)
        self.ax.set_ylabel('amplitude (Hz)', fontsize=25)
        self.ax.plot(x_axis, y_axis)

        self.ids.layout_graph_carrier.clear_widgets()
        self.ids.layout_graph_carrier.add_widget(FigureCanvasKivyAgg(self.fig1))

    def request_map(self):
        if(self.flag_map):
            Clock.unschedule(self.update_map)
            self.ids.bt_screen_setting.disabled = False
            self.ids.bt_screen_graph.disabled = False

            self.ids.bt_update_map.text = "UPDATE MAP"
            self.flag_map = False

        else:
            Clock.schedule_interval(self.update_map, 2)
            self.ids.bt_screen_setting.disabled = True
            self.ids.bt_screen_graph.disabled = True

            self.ids.bt_update_map.text = "UPDATING MAP..."
            self.flag_map = True
            
    def request_graph(self):
        self.update_graph()
        self.dt_slider_distance += 1000
        self.ids.slider_distance.value = float(self.dt_slider_distance / 1000)
        self.dt_distance = int(self.dt_slider_distance / 1000)

    def save_data(self):
        try:
            now = datetime.now().strftime("%d_%m_%Y_%H_%M_%S.sgy")
            with open(now,"wb") as f:
                #np.savetxt(f, self.data_colormap, fmt="%f")
                write_segy(f, self.data_colormap, endian=">")
            print("sucessfully save data")
            self.ids.label_notif.text = "sucessfully save data"
            self.ids.label_notif.color = 0,0,1
        except:
            print("error saving data")
            self.ids.label_notif.text = "error saving data"
            self.ids.label_notif.color = 1,0,0

    def save_graph(self):
        try:
            now = datetime.now().strftime("%d_%m_%Y_%H_%M_%S.jpg")
            self.fig2.savefig(now)
            print("sucessfully save graph")
            self.ids.label_notif.text = "sucessfully save graph"
            self.ids.label_notif.color = 0,0,1
        except:
            print("error saving graph")
            self.ids.label_notif.text = "error saving graph"
            self.ids.label_notif.color = 1,0,0

    def exec_exit(self):
        quit()

    def exec_shutdown(self):
        os.system("shutdown /s /t 1")

    def checkbox_waveform_click(self, instance, value, waves):
        if value == True:
            self.checks_waveform.append(waves)
            waveforms = ''
            for x in self.checks_waveform:
                waveforms = f'{waveforms} {x}'
            self.ids.output_label.text = f'{waveforms} WAVEFORM CHOSEN'
        else:
            self.checks_waveform.remove(waves)
            waveforms = ''
            for x in self.checks_waveform:
                waveforms = f'{waveforms} {x}'
            self.ids.output_label.text = ''
        
        self.dt_waveform = waveforms

    def checkbox_method_click(self, instance, value, meths):
        if value == True:
            self.checks_method.append(meths)
            methods = ''
            for x in self.checks_method:
                methods = f'{methods} {x}'
            self.ids.output_label_method.text = f'{methods} METHOD CHOSEN'
        else:
            self.checks_method.remove(meths)
            methods = ''
            for x in self.checks_method:
                methods = f'{methods} {x}'
            self.ids.output_label_method.text = ''
        
        self.dt_method = methods


class GPRApp(App):
    def build(self):
        self.icon = 'asset/logo.ico'
      
        return MainWindow()

if __name__ == '__main__':
	GPRApp().run()
