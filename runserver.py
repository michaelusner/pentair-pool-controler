from flask import Flask, jsonify, request
#import schedule
import time
from pool_controller import *
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)
pool = PentairCom("/dev/ttyUSB0", logger=app.logger)
pool.start()

def no_cache(ret):
    ret.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    ret.headers["Pragma"] = "no-cache"
    ret.headers["Expires"] = 0
    return ret

@app.route("/pool/status", methods=["GET"])
def get_status():
    app.logger.info("{0}: /pool/status".format(request.remote_addr))
    ret = jsonify(pool.get_status())
    app.logger.info("{0}: Returning: {1}".format(request.remote_addr, ret.response))
    return no_cache(ret)
    
@app.route("/pool/<feature>/<state>", methods=["GET"])
def set_feature(feature, state):
    app.logger.info("{0}: /pool/{0}/{1}".format(request.remote_addr, feature, state))
    res = pool.send_command(pool.FeatureName[feature], state)
    app.logger.info("{0}: Returning {1}".format(request.remote_addr, {feature: res[feature]}))
    return no_cache(jsonify({feature: res[feature]}))

def all_off():
    pool.send_command("pool", "off")
    pool.send_command("spa", "off")
    pool.send_command("pool_light", "off")
    pool.send_command("spa_light", "off")
    pool.send_command("cleaner", "off")
    
if __name__ == '__main__':
    handler = RotatingFileHandler('/home/musner/ha/server.log', maxBytes=10000, backupCount=1)
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)
    app.run(host='0.0.0.0', port=8080, debug=False)
    
    #schedule.every().day.at("00:00").do(all_off,'Shutting down pool')
    #all_off()
    #while True:
    #    schedule.run_pending()
    #    time.sleep(60)
