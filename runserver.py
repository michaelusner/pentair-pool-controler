"""
The flask server for the pool_controller
Michael Usner
"""
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, jsonify, request
from pool_controller import PentairCom

flask_app = Flask(__name__)
pool = PentairCom("/dev/ttyUSB0", logger=flask_app.logger)
pool.start()


def no_cache(ret):
    """ No Cache function """
    ret.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    ret.headers["Pragma"] = "no-cache"
    ret.headers["Expires"] = 0
    return ret


@flask_app.route("/pool/status", methods=["GET"])
def get_status():
    """ Get the pool controller status """
    flask_app.logger.info("%s: /pool/status", request.remote_addr)
    ret = jsonify(pool.get_status())
    flask_app.logger.info("%s: Returning: %s", request.remote_addr, ret.response)
    return no_cache(ret)


@flask_app.route("/pool/<feature>/<state>", methods=["GET"])
def set_feature(feature, state):
    """ Set a feature state """
    flask_app.logger.info("%s: /pool/%s/%s", request.remote_addr, feature, state)
    res = pool.send_command(pool.FeatureName[feature], state)
    flask_app.logger.info("%s: Returning %s", request.remote_addr, {feature: res[feature]})
    return no_cache(jsonify({feature: res[feature]}))


def all_off():
    """ Turn everything off """
    pool.send_command("pool", "off")
    pool.send_command("spa", "off")
    pool.send_command("pool_light", "off")
    pool.send_command("spa_light", "off")
    pool.send_command("cleaner", "off")


if __name__ == '__main__':
    handler = RotatingFileHandler('/home/musner/ha/server.log', maxBytes=10000, backupCount=1)
    handler.setLevel(logging.INFO)
    flask_app.logger.addHandler(handler)
    flask_app.run(host='0.0.0.0', port=8080, debug=False)
    
    #schedule.every().day.at("00:00").do(all_off,'Shutting down pool')
    #all_off()
    #while True:
    #    schedule.run_pending()
    #    time.sleep(60)
