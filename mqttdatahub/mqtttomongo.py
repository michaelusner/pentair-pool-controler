from pymongo import MongoClient
from pprint import pprint
import paho.mqtt.client as mqtt
import paho.mqtt.subscribe as subscribe
import time
import json

from prometheus_client import start_http_server

start_http_server(8000)

from prometheus_client import Gauge
g = Gauge('temp', 'Published MQTT Topic')
gc = Gauge('temp_c', 'Published MQTT Topic')
gf = Gauge('temp_f', 'Published MQTT Topic')
gh = Gauge('humidity', 'Published MQTT Topic')
gp = Gauge('pressure', 'Published MQTT Topic')


mqtthost="192.168.100.8"

# client=mqtt.Client('Mongo')
# client.connect(mqtthost)

client = MongoClient("192.168.100.5")

db=client.sensordata

def on_message_print(client,userdata,message):
   ts=time.time()

   print("Received %s from %s at %s" % (str(message.payload),message.topic,ts))
   iot_data=json.loads(message.payload.decode('utf-8'))
   print("JSON: %s" % (iot_data))
   result=db.env.insert_one(iot_data)
                           
   print('Inserted'+str(iot_data.get("temp_f")))
   g.set(iot_data.get("temp_f"))
   gc.set(iot_data.get("temp_c"))
   gf.set(iot_data.get("temp_f"))
   gh.set(iot_data.get("humidity"))
   gp.set(iot_data.get("pressure"))


subscribe.callback(on_message_print, "house/room1/temp",hostname=mqtthost)

# serverStatusResult=db.command("serverStatus")
# pprint(serverStatusResult)

# TO install
# apt-get install vim
# pip install --upgrade pip
# pip install pymongo
# pip install paho.mqtt
# pip install prometheus_client



