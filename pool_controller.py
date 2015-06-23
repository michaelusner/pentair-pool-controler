from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from time import sleep
from urlparse import urlparse, parse_qs
import datetime
import threading

import serial


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
        AIR_BLOWER = 3
        SPA_LIGHT = 4
        POOL_LIGHT = 5
        POOL = 6
        WATER_FEATURE = 7
        SPILLWAY = 8
        AUX = 9

    FeatureName = {
        'pool': Feature.POOL,
        'spa': Feature.SPA,
        'cleaner': Feature.CLEANER,
        'air_blower': Feature.AIR_BLOWER,
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
        self.status = {}
        self.read_thread.start()

    def __del__(self):
        print "Closing COM port"
        self.port.close()

    def get_packet(self):
        header = [0, 0, 0, 0]
        while header != [255, 0, 255, 165]:
            data = ord(self.port.read())
            header = header[1:] + [data]
        # build up the packet
        packet = [165, ]
        packet += [ord(x) for x in self.port.read(5)]
        packet += [ord(x) for x in self.port.read(packet[-1])]
        checksum = (ord(self.port.read()) * 256) + ord(self.port.read())
        packet_checksum = sum(packet)
        if packet_checksum != checksum:
            print "Checksum is bad: got {0} and calculated {1}".format(checksum, packet_checksum)
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
        print "Sending {0}".format(header + packet)
        self.port.write(header + packet)
        sleep(1)
        if self.status[self.get_feature_name(feature)] == state:
            return True
        return False

    def read_status(self, controller):
        ret = ""
        packet = []
        status = {}
        done = False
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
            print "From: {0}".format(src_controller)
            print "To  : {0}".format(dst_controller)
            print packet
            print
            if len(packet) > 3 and (controller is None or packet[2] == self.Ctrl.BROADCAST):
                done = True

        data_length = packet[5]
        if data_length > 8:
            equip1 = "{0:08b}".format(packet[self.Equip1])
            equip2 = "{0:08b}".format(packet[self.Equip2])
            print "Equip1: {0}".format(equip1)
            print "Equip2: {0}".format(equip2)
            print
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
        else:
            print
        return status

    def get_broadcast_status(self):
        "Read broadcast thread is running"
        while running:
            self.status = self.read_status(self.Ctrl.BROADCAST)


class myHandler(BaseHTTPRequestHandler):
    pentair = PentairCom('com6')

    def get_toggle_switch(self, title, name, value):
        return """<tr><td valign="center"><label for="{1}">{0}</label></td>
                    <td valign="center">
                        <input type="checkbox" data-role="flipswitch" data-mini="true" name="{1}" id="{1}" {2}>
                    </td>
                </tr>
        """.format(title, name, "checked" if value else "",
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

        elif self.path.startswith('/feature?'):
            if len(params) != 0:
                for param in params:
                    if self.pentair.send_command(self.pentair.FeatureName[param], True if params[param][0] == 'true' else False):
                        self.send_response(200)
                    else:
                        self.send_response(400)

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        status = self.pentair.status
        status_table = """
            <h4>Air: {2}&deg; Water: {1}&deg;
            </h4>""".format(status['time'] if 'time' in status else 'None',
                            status['water_temp'] if 'water_temp' in status else 'None',
                            status['air_temp'] if 'air_temp' in status else 'None')

        status_table += "<table>"
        if 'pool' in status:
            status_table += self.get_toggle_switch("Pool", 'pool', status['pool'])
        if 'spa' in status:
            status_table += self.get_toggle_switch("Spa", 'spa', status['spa'])
        if 'cleaner' in status:
            status_table += self.get_toggle_switch("Cleaner", 'cleaner', status['cleaner'])
        if 'blower' in status:
            status_table += self.get_toggle_switch("Air Blower", 'blower', status['blower'])
        if 'spa_light' in status:
            status_table += self.get_toggle_switch("Spa Light", 'spa_light', status['spa_light'])
        if 'pool_light' in status:
            status_table += self.get_toggle_switch("Pool Light", 'pool_light', status['pool_light'])
        if 'water_feature' in status:
            status_table += self.get_toggle_switch("Water Feature", 'water_feature', status['water_feature'])
        if 'spillway' in status:
            status_table += self.get_toggle_switch("Spillway", 'spillway', status['spillway'])
        if 'aux' in status:
            status_table += self.get_toggle_switch("Aux", 'aux', status['aux'])

        status_table += "</table>"
        body = """<html>
<head>
    <title>My Page</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="http://code.jquery.com/mobile/1.4.5/jquery.mobile-1.4.5.min.css">
    <script src="http://code.jquery.com/jquery-1.11.3.min.js"></script>
    <script src="http://code.jquery.com/mobile/1.4.5/jquery.mobile-1.4.5.min.js"></script>>
    <style>
        table {{
            border-collapse: collapse;
        }}

        table, td, th {{
            border: 1px solid black;
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
        $.ajax({{url: url}}).done(function() {{  }});
    }}
  $( document ).ready(function() {{
    $("input[type='checkbox']").bind( "change", function(event, ui) {{
        httpGet("http://192.168.1.2/feature?" + this.name + "=" + this.checked);
    }});
  }});

  </script>
</head>
<body>
<div data-role="page">
    <div data-role="content">
        <!--<div id="overlay">
            <img id='wait' src='wait.gif' style='visibility: hidden;'>
        </div>-->
        <div id="content">
        {0}
        </div>
    </div>
</div>
</body>
</html>""".format(status_table)
        self.wfile.write(body)

    def log_request(self, code=None, size=None):
        print('Request from {0}'.format(self.client_address[0]))

    def log_message(self, format, *args):
        print('Message')


if __name__ == "__main__":
    Protocol = "HTTP/1.0"
    port = 80
    server_address = ('192.168.1.2', port)
    httpd = HTTPServer(server_address, myHandler)
    try:
        print 'Started httpserver on port ', port
        httpd.serve_forever()
    except KeyboardInterrupt:
        print '^C received, shutting down monitor thread and web server'
        running = False
        httpd.socket.close()
