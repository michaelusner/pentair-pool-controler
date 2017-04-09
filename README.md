# pool
Code for reading and controlling Pentair EasyTouch via RS485/RS232

This utility is meant to be run as a service on a system utilizing a RS485 reader.
In my case, it's a Rasberry Pi 3 with a USB RS232/RS485 connector.
A single CAT5 line (using only 2 wires) extends from the pool controller to the Rasberry Pi.

This service integrates with a SmartThings driver to allow controlling the Pentair 
equipment via the SmartThings app.  You can activate pool features simply by issuing
GET requests to the correct endpoints.

NOTE: since the services are exposed on port 8080, you will need to take care that
this port is not exposed to the outside world on your router.  Also, there's no authentication
mechanism - anyone on your home network *could* control your pool if they knew how.

The service assumes your COM port is /dev/ttyUSB0 so you will need to modify this
depending on your system and OS.

When you run the service, pool controller endpoints will be exposed:
/pool/status
  Returns all features and their statuses
  Example:
    $ curl http://192.168.1.13:8080/pool/status
    Response: {
      "air_blower": "off",
      "air_temp": 74,
      "aux": "off",
      "cleaner": "on",
      "destination": "Broadcast",
      "last_update": "Sun, 09 Apr 2017 10:24:33 GMT",
      "pool": "on",
      "pool_light": "off",
      "source": "Main",
      "spa": "off",
      "spa_light": "off",
      "spillway": "off",
      "time": "11:00",
      "water_feature": "off",
      "water_temp": 74
    }
  
/pool/-feature-/-state-
  Set a feature to an on/off state
  Examples:
    Turn the spa on
    $ curl http://192.168.1.13:8080/pool/spa/on
    Response: {
      "spa": "on"
    }
    
    Turn the spa off
    $ curl http://192.168.1.13:8080/pool/spa/off
    Response: {
      "spa": "off"
    }

    Turn the pool light on
    $ curl http://192.168.1.13:8080/pool/pool_light/on
    Response: {
      "spa": "on"
    }
    
    The list of features can be found above in the /pool/status response.
