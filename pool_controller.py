from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from time import sleep
from urlparse import urlparse, parse_qs
import datetime
import json
import logging
import threading

import serial

from yamaha_rx675 import YamahaRx675
import pushbullet
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(levelname)-8s %(message)s',
                    datefmt='%a, %d %b %Y %H:%M:%S')


def to_int(x):
    return int(x, 16)


def bool_to_status(status):
    return "On" if int(status) else "Off"

running = True


class PentairCom(object):
    Equip1 = 8
    Equip2 = 9
    WaterTemp = 20
    AirTemp = 24
    Hour = 6
    Minute = 7

    class State:
        OFF = 0
        ON = 1

    class Ctrl:
        MAIN = 0x10
        REMOTE = 0x20
        PUMP1 = 0x60
        BROADCAST = 0x0f

    Controller = {
        Ctrl.MAIN: "Main",
        Ctrl.REMOTE: "Remote",
        Ctrl.PUMP1: "Pump1",
        Ctrl.BROADCAST: "Broadcast"
    }

    class Feature:
        SPA = 1
        CLEANER = 2
        BLOWER = 3
        SPA_LIGHT = 4
        POOL_LIGHT = 5
        POOL = 6
        WATER_FEATURE = 7
        SPILLWAY = 8
        AUX = 9

        # From: Remote
        # To  : Main
        #[165, 31, 16, 32, 136, 4, pool89, spa97, 4, 0]

    FeatureName = {
        'pool': Feature.POOL,
        'spa': Feature.SPA,
        'cleaner': Feature.CLEANER,
        'blower': Feature.BLOWER,
        'spa_light': Feature.SPA_LIGHT,
        'pool_light': Feature.POOL_LIGHT,
        'water_feature': Feature.WATER_FEATURE,
        'spillway': Feature.SPILLWAY,
        'aux': Feature.AUX
    }

    def __init__(self, com):
        self.com = com
        self.port = serial.Serial(com, 9600)
        self.read_thread = threading.Thread(target=self.get_broadcast_status)
        self.pump_status = {}
        self.status = {}
        self.last_status = {}
        self.read_thread.start()

    def __del__(self):
        self.port.close()

    def get_packet(self):
        header = [0, 0, 0, 0]
        while header != [255, 0, 255, 165]:
            text = self.port.read()
            if len(text) == 0:
                continue
            data = ord(text)
            header = header[1:] + [data]
        # build up the packet
        packet = [165, ]
        packet += [ord(x) for x in self.port.read(5)]
        packet += [ord(x) for x in self.port.read(packet[-1])]
        checksum = (ord(self.port.read()) * 256) + ord(self.port.read())
        packet_checksum = sum(packet)
        if packet_checksum != checksum:
            logging.warn("Checksum is bad: got {0} and calculated {1}".format(checksum, packet_checksum))
            return []
        return packet

    def get_feature_name(self, feature_number):
        return {v: k for k, v in self.FeatureName.items()}[feature_number]

    def send_command(self, feature, state):
        header = [0x00, 0xff]
        packet = [165, 31, self.Ctrl.MAIN, self.Ctrl.REMOTE, 134, 2, feature, 1 if state else 0]
        checksum = sum(packet)
        packet.append(checksum / 256)
        packet.append(checksum % 256)
        logging.info("Sending {0}".format(header + packet))
        self.port.write(header + packet)
        sleep(1)
        if self.status[self.get_feature_name(feature)] == state:
            return True
        return False

    def notify_status(self):
        ignore = ['last_update', 'time', 'air_temp', 'water_temp']
        if len(self.last_status) == 0:
            self.last_status = self.status
        msg = ''
        for k, v in self.status.items():
            if k in self.last_status and v != self.last_status[k] and k not in ignore:
                if not self.last_status[k] and v:
                    state = 'Off -> On'
                else:
                    state = 'On -> Off'
                msg += '{0}: {1}\n'.format(k, state)
            self.last_status[k] = v
        if len(msg) > 0:
            logging.info("Sending message:")
            logging.info(msg)
            pushbullet.send_message('S5', 'Pool', msg)

    def read_status(self, controller):
        ret = ""
        packet = []
        status = {}
        done = False
        src_controller = None
        dst_controller = None
        while not done:
            packet = self.get_packet()
            if len(packet) > 3:
                dst = packet[2]
                if dst in self.Controller:
                    dst_controller = self.Controller[dst]
                else:
                    dst_controller = dst
                src = packet[3]
                if src in self.Controller:
                    src_controller = self.Controller[src]
                else:
                    src_controller = src
            logging.info("From: {0}".format(src_controller))
            logging.info("To  : {0}".format(dst_controller))
            
            # if message is from pump and contains status
            logging.info("packet: {0}".format(packet[0:6]))
            if packet[0:6] == [165, 0, 16, 96, 7, 15]:
                self.pump_status['power'] = ("On" if packet[6] == 0x0a else "Off")
                self.pump_status['watts'] = int("{0:02x}{1:02x}".format(packet[9], packet[10]), 16)
                self.pump_status['rpm'] = int("{0:02x}{1:02x}".format(packet[11], packet[12]), 16)
                
                logging.info("**** Pump Status ****")
                logging.info("Started: {0}".format(True if packet[6] == 0x0a else False))
                #logging.info("Feature 1: {0}".format(packet[7]))
                #logging.info("Drive State: {0}".format(packet[8]))
                logging.info("Power: {0} Watts".format(int("{0:02x}{1:02x}".format(packet[9], packet[10]), 16)))
                logging.info("RPM: {0}".format(int("{0:02x}{1:02x}".format(packet[11], packet[12]), 16)))
                #logging.info("GPM: {0}".format(packet[13]))
                #logging.info("%: {0}".format(packet[14]))
                #logging.info("Err: {0}".format(packet[16]))
                #logging.info("TMR: {0}".format(packet[18]))
                #logging.info("Clck: {0}".format(int("{0:02x}{1:02x}".format(packet[19], packet[20]), 16)))
            logging.info(["{0:02x}".format(int(i)) for i in packet])
            if len(packet) > 3 and (controller is None or packet[2] == self.Ctrl.BROADCAST):
                done = True

        data_length = packet[5]
        if data_length > 8:
            equip1 = "{0:08b}".format(packet[self.Equip1])
            equip2 = "{0:08b}".format(packet[self.Equip2])
            logging.info("Equip1: {0}".format(equip1))
            logging.info("Equip2: {0}".format(equip2))

            if data_length == 29:
                status['last_update'] = datetime.datetime.now()
                status['source'] = src_controller
                status['destination'] = dst_controller
                status['time'] = "{0:02d}:{1:02d}".format(packet[6], packet[7])
                status['spillway'] = bool(int(equip1[0:1]))
                status['pool'] = bool(int(equip1[2:3]))
                status['spa'] = bool(int(equip1[7:8]))
                status['blower'] = bool(int(equip1[5:6]))
                status['pool_light'] = bool(int(equip1[3:4]))
                status['spa_light'] = bool(int(equip1[4:5]))
                status['cleaner'] = bool(int(equip1[6:7]))
                status['water_feature'] = bool(int(equip1[1:2]))
                status['aux'] = bool(int(equip2[7:8]))
                if len(packet) >= self.WaterTemp:
                    status['water_temp'] = int(packet[self.WaterTemp])
                if len(packet) >= self.AirTemp:
                    status['air_temp'] = int(packet[self.AirTemp])
                self.notify_status()

        return status

    def get_broadcast_status(self):
        "Read broadcast thread is running"
        while running:
            logging.info("*************************************************************")
            self.status = self.read_status(self.Ctrl.BROADCAST)


class myHandler(BaseHTTPRequestHandler):
    pentair = PentairCom('com6')
    yamaha = YamahaRx675('tuner')

    def get_toggle_switch(self, controller, title, name, value):
        return """<td valign="center"><label for="{2}">{1}</label></td>
                    <td valign="center">
                        <input type="checkbox" data-role="flipswitch" data-mini="true" class="{0}" name="{2}" id="{2}" {3}>
                    </td>
        """.format(controller, title, name, "checked" if value else "",
                   "checked" if not value else "")

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        if self.path == '/favicon.ico':
            self.send_response(200)
            return
        elif self.path == '/wait.gif':
            self.send_response(200)
            self.send_header('Content-type', 'image/gif')
            self.end_headers()
            try:
                f = open('wait.gif', 'rb')
                self.wfile.write(f.read())
            except IOError:
                self.send_error(404, 'File Not Found: {0}'.format(self.path))
            return

        elif self.path.startswith('/tuner'):
            if self.path.startswith('/tuner/pandorainfo'):
                info = self.yamaha.get_pandora_play_info()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(info))
                return
            for param in params:
                if param == 'power':
                    if params[param][0] == 'true':
                        self.yamaha.zone2.power_on()
                    else:
                        self.yamaha.zone2.power_off()
                if param == 'pandora':
                    if params[param][0] == 'true':
                        self.yamaha.zone2.power_on()
                        self.yamaha.zone2.input = 'Pandora'
                        self.yamaha.zone2.volume = -25.0
                if param == 'vol' and params[param][0] == 'up':
                    self.yamaha.zone2.volume_up()
                if param == 'vol' and params[param][0] == 'down':
                    self.yamaha.zone2.volume_down()
            self.send_response(200)
            return

        elif self.path.startswith('/pool?'):
            if len(params) != 0:
                for param in params:
                    if self.pentair.send_command(self.pentair.FeatureName[param], True if params[param][0] == 'true' else False):
                        self.send_response(200)
                    else:
                        self.send_response(400)
        elif self.path.startswith('/pump'):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(json.dumps(self.pentair.pump_status))
            return
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        status = self.pentair.status
        pool_table = """<h4>Air: {2}&deg; Water: {1}&deg;</h4>
            """.format(status['time'] if 'time' in status else 'None',
                       status['water_temp'] if 'water_temp' in status else 'None',
                       status['air_temp'] if 'air_temp' in status else 'None')
        pool_table += "<table><tr><td>Pump</td><td id='pump_power'></td></tr>"
        pool_table += "<tr><td>Watts</td><td id='pump_watts'></td></tr>"
        pool_table += "<tr><td>RPM</td><td id='pump_rpm'></td></tr>"
        pool_table += "</table>"
        pool_table += "<table>"
        if 'pool' in status:
            pool_table += "<tr>" + self.get_toggle_switch('pool', "Pool", 'pool', status['pool'])
        if 'spa' in status:
            pool_table += self.get_toggle_switch('pool', "Spa", 'spa', status['spa']) + "</tr>"
        if 'cleaner' in status:
            pool_table += "<tr>" + self.get_toggle_switch('pool', "Cleaner", 'cleaner', status['cleaner'])
        if 'blower' in status:
            pool_table += self.get_toggle_switch('pool', "Air Blower", 'blower', status['blower']) + "</tr>"
        if 'spa_light' in status:
            pool_table += "<tr>" + self.get_toggle_switch('pool', "Spa Light", 'spa_light', status['spa_light'])
        if 'pool_light' in status:
            pool_table += self.get_toggle_switch('pool', "Pool Light", 'pool_light', status['pool_light']) + "</tr>"
        if 'water_feature' in status:
            pool_table += "<tr>" + self.get_toggle_switch('pool', "Water Feature", 'water_feature', status['water_feature'])
        if 'spillway' in status:
            pool_table += self.get_toggle_switch('pool', "Spillway", 'spillway', status['spillway']) + "</tr>"
        if 'aux' in status:
            pool_table += "<tr>" + self.get_toggle_switch('pool', "Aux", 'aux', status['aux']) + "<td></td></tr>"
        pool_table += "<tr>" + self.get_toggle_switch('tuner', "Pandora", 'pandora', self.yamaha.zone2.state['Power_Control']['Power'] == 'On' and self.yamaha.zone2.state['Input']['Input_Sel'] == "Pandora") + "<td>Pump Watts</td><td></td></tr>"
        pool_table += """<tr><td><button id="volup">Volume Up</button></td><td>Pump RPM</td><td></td></tr>"""
        pool_table += """<tr><td><button id="voldown">Volume Down</button><td></td></td></tr>"""
        pool_table += """</table><table><tr><td>Station</td><td><span id="station">None</span></td><td></td></tr>"""
        pool_table += """<tr><td>Album</td><td><span id="album">None</span></td><td></td></tr>"""
        pool_table += """<tr><td>Track</td><td><span id="track">None</span></td><td></td></tr>"""
        pool_table += "</table>"

        body = """<html>
<head>
    <title>Pool</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="http://code.jquery.com/mobile/1.4.5/jquery.mobile-1.4.5.min.css">
    <script src="http://code.jquery.com/jquery-1.11.3.min.js"></script>
    <script src="http://code.jquery.com/mobile/1.4.5/jquery.mobile-1.4.5.min.js"></script>>
    <style>
        table {{
            border-collapse: collapse;
        }}

        table, td, th {{
            border: 0px solid black;
            padding: 5px;
        }}
        #overlay {{
            width: 100%;
            height: 100%;
            position: absolute;
            top: 250;
            left: 100;
            z-index: 10;
        }}
    </style>
    <script>

    function httpGet(url)
    {{
        $.ajax({{url: url}}).done(function() {{  }})
         .fail(function() {{ alert("Failed to set feature state.  Check server."); }});
    }}
    $( document ).ready(function() {{
      $(".pool").bind( "change", function(event, ui) {{
          httpGet("http://192.168.1.2/pool?" + this.name + "=" + this.checked);
      }});
      $(".tuner").bind( "change", function(event, ui) {{
          alert(this.name + "-" + this.checked);
          httpGet("http://192.168.1.2/tuner?" + this.name + "=" + this.checked);
      }});
      $("#volup").click(function() {{
          httpGet("http://192.168.1.2/tuner?vol=up");
      }});
      $("#voldown").click(function() {{
          httpGet("http://192.168.1.2/tuner?vol=down");
      }});
      setInterval(function() {{
        $.getJSON("http://192.168.1.2/pump").done(function(data) {{
            $("#pump_power").text(data.power);
            $("#pump_watts").text(data.watts);
            $("#pump_rpm").text(data.rpm);
        }}).fail(function() {{  }});
        $.ajax({{url: "http://192.168.1.2/tuner/pandorainfo"}}).done(function(data) {{
            $("#station").text(data.station);
            $("#album").text(data.album);
            $("#track").text(data.track);
        }}).fail(function() {{  }});
      }}, 5000);
    }});

  </script>
</head>
<body>
<div data-role="page">
    <div id="pool-content" style="float: left">
        {0}
    </div>
</div>
</body>
</html>""".format(pool_table)
        self.wfile.write(body)

    def log_request(self, code=None, size=None):
        logging.info('Request from {0}'.format(self.client_address[0]))

    def log_message(self, format, *args):
        logging.info('Message')

if __name__ == "__main__":
    Protocol = "HTTP/1.0"
    port = 80
    server_address = ('192.168.1.2', port)
    httpd = HTTPServer(server_address, myHandler)
    try:
        logging.info('Started httpserver on port {0}'.format(port))
        httpd.serve_forever()
    except KeyboardInterrupt:
        logging.info('------------ ^C received, shutting down monitor thread and web server ------------')
        running = False
        httpd.socket.close()
