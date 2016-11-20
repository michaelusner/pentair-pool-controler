import array
from time import sleep
import datetime
import threading
import serial
import logging
import unittest
from itertools import combinations
from random import shuffle, choice

logging.basicConfig(format='%(asctime)s %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def to_int(x):
    return int(x, 16)


def bool_to_status(status):
    return "On" if int(status) else "Off"

class PentairCom(threading.Thread):
    timeout = 5
    ready = False
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

    state = {0: "off", 1: "on"}
    
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

    FeatureValue = {v:k for v,k in FeatureName.items()}
    
    def __init__(self, com, logger=logger):
        super(PentairCom, self).__init__()
        self.logger=logger
        self.com = com
        self.port = serial.Serial(com, 9600)
        sleep(2)

    def __del__(self):
        self.logger.info("Closing COM port")
        self.port.close()

    def get_packet(self):
        header = [0, 0, 0, 0]
        while header != [255, 0, 255, 165]:
            data = ord(self.port.read())
            header = header[1:] + [data]
        # build up the packet
        packet = [165, ]
        packet += [x for x in self.port.read(5)]
        packet += [x for x in self.port.read(packet[-1])]
        checksum = (ord(self.port.read()) * 256) + ord(self.port.read())
        packet_checksum = sum(packet)
        if packet_checksum != checksum:
            self.logger.error("Checksum is bad: got {0} and calculated {1}".format(checksum, packet_checksum))
            self.logger.error("Packet is {0}".format(packet))
            return []
        return packet

    def get_feature_name(self, feature_number):
        return {v: k for k, v in self.FeatureName.items()}[feature_number]

    def send_command(self, feature, state):
        start = datetime.datetime.now()
        retry = 5
        feature_name = self.get_feature_name(feature)
        self.logger.info("Setting {0} to {1}".format(feature_name, state))
        header = [0x00, 0xff]
        packet = [165, 31, self.Ctrl.MAIN, self.Ctrl.REMOTE, 134, 2, feature, 1 if state=="on" else 0]
        checksum = sum(packet)
        packet.append(int(checksum / 256))
        packet.append(checksum % 256)
        self.logger.debug("Sending {0}".format(header + packet))
        p = array.array('B', header + packet)
        self.port.write(p)
        #sleep(0.3)
        start = datetime.datetime.now()
        status = self.get_status()
        self.logger.info("{0} state is {1}".format(feature_name, status[feature_name]))
        while  status[feature_name] != state and retry:
            self.port.write(p)
            status = self.get_status()
            self.logger.info(status)
            if retry != 5:
                self.logger.info("Retry {0}".format(5-retry))
            retry -= 1
        if (datetime.datetime.now() - start).total_seconds() > self.timeout:
                self.logger.error("Timeout while waiting for value")
                self.logger.error(status)
                raise AssertionError("Timeout while waiting for value")
        duration = (datetime.datetime.now() - start).total_seconds()
        self.logger.info("Set {0} to {1} in {2:.2f}s".format(feature_name, state, duration))
        return self.status
        
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
                self.logger.debug("From: {0}".format(src_controller))
                self.logger.debug("To  : {0}".format(dst_controller))
                self.logger.debug(packet)
                if len(packet) > 3 and (controller is None or packet[2] == self.Ctrl.BROADCAST):
                    done = True

        data_length = packet[5]
        if data_length > 8:
            equip1 = "{0:08b}".format(packet[self.Equip1])
            equip2 = "{0:08b}".format(packet[self.Equip2])
            self.logger.debug("Equip1: {0}".format(equip1))
            self.logger.debug("Equip2: {0}".format(equip2))
            status['last_update'] = datetime.datetime.now()
            status['source'] = src_controller
            status['destination'] = dst_controller
            status['time'] = "{0:02d}:{1:02d}".format(packet[6], packet[7])
            status['spillway'] = self.state[int(equip1[0:1])]
            status['pool'] = self.state[int(equip1[2:3])]
            status['spa'] = self.state[int(equip1[7:8])]
            status['air_blower'] = self.state[int(equip1[5:6])]
            status['pool_light'] = self.state[int(equip1[3:4])]
            status['spa_light'] = self.state[int(equip1[4:5])]
            status['cleaner'] = self.state[int(equip1[6:7])]
            status['water_feature'] = self.state[int(equip1[1:2])]
            status['aux'] = self.state[int(equip2[7:8])]
            if len(packet) >= self.WaterTemp:
                status['water_temp'] = int(packet[self.WaterTemp])
            if len(packet) >= self.AirTemp:
                status['air_temp'] = int(packet[self.AirTemp])
        if self.ready != True:
                self.ready = True
        return status

    def run(self):
        while True:
            self.status = self.read_status(self.Ctrl.BROADCAST)

    def get_status(self):
        self.ready = False
        while not self.ready:
            sleep(0.1)
        return self.status

class MyTest(unittest.TestCase):
    def test_modes(self):
        feature_list = [
            PentairCom.Feature.SPA,
            PentairCom.Feature.CLEANER,
            PentairCom.Feature.AIR_BLOWER,
            PentairCom.Feature.SPA_LIGHT,
            PentairCom.Feature.POOL_LIGHT,
            PentairCom.Feature.POOL,
            PentairCom.Feature.WATER_FEATURE,
            PentairCom.Feature.SPILLWAY,
            PentairCom.Feature.AUX
        ]
        x = PentairCom('/dev/ttyUSB0')
        x.start()
        f = [x for x in combinations(feature_list, 4)]
        shuffle(f)
        for cmb in f:
            for feature in cmb:
                state = choice([0,1])
                res = x.send_command(feature, state)
                logging.info(res)
                assert(res[x.get_feature_name(feature)] == state)
                sleep(0.5)

if __name__ == "__main__":
    unittest.main()
    
    
