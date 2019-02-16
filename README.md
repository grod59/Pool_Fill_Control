# Pool_Fill_Control V3.5.0 (2019-02-16)
> Major updates to data storage using MySQL and InfluxDB and away from flat files. Please see the bottom of this readme for more updates!
<br>
<i>Raspberry Pi / Arduino / Python / Alexa Project to automate pump management and filling of swimming pool along with tracking of various temperature and humidity sensors, smart water meters and more. Includes Flask based Web Interface and Alexa Skill.</i> 
<br><br>

This software is not really intended to be "plug-and-play" but rather sharing of code, hardware and sensor ideas that you can use as a starting point in your own pool management system. *Enjoy!*

While this readme is more specific to the code portion of the project, an [in-depth writeup of the entire project](https://www.hackster.io/user3424878278/pool-fill-control-119ab7) from start to finish is available on Hackster.io with tons more detail and pictures!

<br>

<br>
<p align="center">
 <b>Updated Web Interface created and managed with Flask</b>
</p>

![alt tag](https://github.com/rjsears/Pool_Fill_Control/blob/V3.5/pictures/pool_control_web_interface_v350.jpg?raw=true)

<br>

This pool control software system was designed to automate and manage some everyday pool management tasks. It started out with just filling the pool, hence the name of the repo: pool_fill_control. It grew into far more than that and now is integrated into a variety of system around our home. Here is a current (as of V3.5.0) list of items managed or monitored by the system:
 <br>
- Pool Water Level (with auto and manual fill functions)
- Pool Water Level Sensor Temperature, Humidity & Battery Level
- Sprinkler System - Tracking Only (On or Off)
- Pool Temperature
- Pool Temperature Sensor Temperature, Humidity & Battery Level
- Acid Tank Level
- Pool pH & ORP
- Pool Filter PSI
- Pool Pump Parameters (GPM, RPM, Watts)
- Pool Pump Management (Start, Stop, Change Running Programs)
- Pool Electrical Panel Electrical Usage
- Pool water usage during fill and overall water usage
- Pool Fill Timer while filling
- Pool filling (automatically, manually, or manually via Alexa skill)
- Alexa Skill via Flask-Ask
- Alexa readback of all system parameters
- Alexa ability to fill or stop filling pool
- Household Electrical Usage
- Household Solar Production
- Notifications via SMS, E-Mail, Pushbullet, Logging and Debug
 
<br>
The basic premise of the system is pretty simple. Utilizing a variety of low-power arduino clones as system "sensors" we measure the water level of the pool and check to see if the sprinklers are running. If the water is low and the sprinklers are not running, we turn on a transformer that powers a sprinkler valve and we refill the pool. Once the pool has been filled to a specific level, we shut off the water. Since we fill from our irrigation system, we need to know if the sprinklers are running. If they are, we do not have enough water pressure to run several zones at once so the system will keep checking and will refill the pool once the sprinklers are done.
<br><br>

Over time I added temperature monitoring, pH and ORP monitoring (but not control), Acid tank level monitoring, pool filter pressure monitoring, electrical (including solar) monitoring and pool pump management utilizing Russell Goldin's [poolController Software](https://github.com/tagyoureit/nodejs-poolController). Because much of our house has other sensors I included monitoring of battery levels of various temperature and humidity sensors around the house that have nothing to do with the pool, but since I had the system in place to monitor and alert for these I went ahead and added them anyway. This is the same for overall power utilization and solar production.

I have also been working on adding in Alexa integration and learning how to build Alexa skills around the house. I have created a skill that allows you to query the system for all of the pool stats as well as to start and stop filling of the pool. The kids can also ask it if it is ok to go swimming and Alexa will ask them for the temperature they like the water, compare that to the current water temperature and then let them know if it is ok to go swimming. More a programming challenge than anything else. The Alexa interface is coded using the [Flask-Ask python framework](https://github.com/johnwheeler/flask-ask), but as I understand it, Flask-Ask is no longer being maintained so I may have to move to the much more difficult Pythin Alexa SDK in the future.

<br>

![alt tag](https://github.com/rjsears/Pool_Fill_Control/blob/V3.5/pictures/pool_control_Alexa_interface_01_v350.jpeg)

<br>

![alt tag](https://github.com/rjsears/Pool_Fill_Control/blob/V3.5/pictures/screen%202016-05-30%20at%201.50.40%20PM.jpg?raw=true)
![alt tag](https://github.com/rjsears/Pool_Fill_Control/blob/V3.5/pictures/PFC_Internal_Connected.jpg?raw=true)
![alt tag](https://github.com/rjsears/Pool_Fill_Control/blob/V3.5/pictures/pc_external.jpg?raw=true)

<br>


###### Our system relies on a *lot* of external applications and hardware. Depending on how you plan on setting up your system you may or may not need all of these applications or hardware devices. It is outside the scope of this readme to go through the installation procedures of the various software system and setup of hardware, but you can always email if you run into trouble:

1. Raspberry Pi
   - The "brains" behind the operation. Our main python code runs on a [Raspberry Pi Model 3](https://www.raspberrypi.org/) with a 65GB SD Card.
2. OpenEnergyMonitor's EmonPi
   - A [RaspberryPi powered hardware device](https://guide.openenergymonitor.org/setup/) that allows for electrical and temperature monitoring as well as being a hub for the reception of all wireless sensor data. Manages storing data to MySQL for use by other systems as well as forwarding this data to other EmonCMS instances (locally or in the cloud).
3. OpenEnergyMonitor's Open Source Energy Monitoring Platform [(EmonCMS)](https://emoncms.org/)
   - This system gathers and writes various sensor data to a MySQL database for use by pool_fill_control. We utilize 433Mhz radios from our sensors and transmit our data to EmonCMS. From there we can access it from our program. This runs on our EmonPi as well as on several "backup" servers to house our environmental data.
4. LowPowerLab's [MightyHat](https://lowpowerlab.com/guide/mightyhat/)
   - MightyHat is a Raspberry Pi Hat with that makes it easy to build a compact, robust, battery backed-up gateway for the internet of things. It accepts RFM69W/HW/HCW or LoRa transceivers and acts as a power controller and UPS for the RaspberryPi. This is on the main RaspberryPi that runs our system at the pool.
5. LowPowerLab's [R6 Moteino](https://lowpowerlab.com/shop/moteinousb)
   - The Moteino is a super-low-power Arduino clone that incorpoprates a 433Mhz FSK (RFM69HCW) transceiver which transmits data to our EmonPi.
6. [Atlas Scientific](https://www.atlas-scientific.com/) pH and ORP Probes and boards
   - USB input boards and probes for [pH](https://www.atlas-scientific.com/ph.html) and [ORP](https://www.atlas-scientific.com/orp.html).
7. pH and ORP Flow Cell
   - Flow cell purchased from [Sunplay](https://sunplay.com/products/ips-controllers-flow-cell-complete-fc100g) to house our pH and ORP sensors as well as to provide water flow sensing.
8. [Elecall Stainless Steel Tank Water Level Sensor Float Switch](https://www.amazon.com/gp/product/B01M1HAN4O)
   - Stainless steel dual level water level sensor used to monitor the water level in the pool so we know when to refill it. Has "low" and a "high" side floats that are monitored with an EmonTH sensor.
9. [MySQL](https://www.mysql.com/)
   - Used by EmonCMS as well as our pool control system to store both environmental data as well as system states and other data.
10. [InfluxDB](https://github.com/influxdata/influxdb)
    - Used to store temperature, humidity, pH, ORP and electrical data specifically for graphing by Grafana. 
11. [Grafana](https://grafana.com/)
    - Used to build grahing interfaces for web interface via i-frames for our web interface (pH & ORP) as well as other system graphing needs.
12. [Flask](http://flask.pocoo.org/)
    - Python Microframework used to build the front-end web interface for our pool control project.
13. [Flask-Ask](https://github.com/johnwheeler/flask-ask)
    - Alexa skills kit for Python by John Wheeler. (Will be moving away from Flask-Ask as the rumor is that John is no longer maintaining the project). 

###### EmonCMS software EmonPi Hub and EmonTH sensors comprise the core of our sensor monitoring capabilities! 
<img src="https://github.com/rjsears/Pool_Fill_Control/blob/V3.5/pictures/emonCMS.jpg" width="500" height="300">

We utilize the EmonPI as our wireless hub:<br>
<img src="https://github.com/rjsears/Pool_Fill_Control/blob/V3.5/pictures/emonPI.jpg" width="500" height="300">





The pool can be filled automatically, or it can be filled by pressing a manual fill button.  A cutout switch on the system prevents the relay from opening the sprinkler valve in the event there is a problem with the system. 

Because our irrigation system is required to have a backfeed prevention vacuum breaker system already, I choose to connect our pool fill project to our irrigation system. Because of this, I needed a way to make sure I did not try to fill the pool while the sprinklers are running. I can check this in two ways, the first is a simple “black out timer” that you would set to the times your sprinklers run, or with an API integration with the Rachio sprinkler system (which we have).  In this case, before we fill the pool, we query the API and determine in real time if our sprinklers are running.

Because we fill the pool via existing pool water lines, I do not want to fill the pool while my pool pump is running. I monitor all electrical usage in the house utilizing OpenEnergyMonitor’s (OEM) emoncms along with hardware from both OEM as well as Brultech. This information is stored in a MySQL database. I simply query that database and see how many watts are currently being used by my pool subpanel and if it is over a certain amount, I do not allow the pool to be filled (automatically or manually).

In case of a problem with the software or hardware, I have a timer that runs anytime we are filling the pool automatically. If we go over a preset amount of time, we force the sprinkler valve closed, log the error and send a notification.
There is a manual fill button that allows me to fill the pool when I want to fill it as opposed to waiting for the automatic system to do it for me. Because it is manual, it does not care how long it will run and is not subject to the run timer. However, it is subject to the sprinkler and pump controls. 

I am not a programmer and this is just some fun stuff that I have been working on in my spare time. Eventually I will expand this to include a full monitoring system of the pool chemicals and other automation including a web interface to view all of the system parameters.

Currrently the only notifications that are included are logging and pushbullet.

V2.4 now includes 5 different system status LEDs. These include:
 - Sprinklers Running (BLUE)
 - Pool Pump Running (YELLOW) (requires some type of external power monitor)
 - System OK (GREEN)
 - System ERROR (RED)
 - Pool Filling (BLUE)
<br><br>
 
V2.5 (2016-06-04)
 - Added additional DPDT switch that physically breaks power to the sprinkler fill valve
   as well as sets notifications, resets the fill relay (if in use) and logs the event.
 - Added additional LED for the above switch to show when we have manually cut off power
   to our sprinkler fill valve.
 - Centralized all Pushbullet notifications
 - Various bug fixes

<br><br>
V2.6 (2016-06-05)
- Code Optimization
- Bug Fixes
- Added Watchdog support - if no watchdog notification every 70 seconds, script restarts
 
<br>
V2.7 (2016-06-11)
- Added Atlas Scientific pH and ORP probes to system. They are, for now, just logging to log file (logger.info).

<br>

V2.8 (2016-06-13)
- Updated how the pH and ORP probes are read.
- Added ability to log to one or more Emoncms servers, locally or remote

<br>

V2.9 (2016-06-18)
- Eliminated alerting.py file, added contents to pooldb.py file.
- Added a lot of DEBUG printing to STDOUT if DEBUG == 1 is set. 
- Moved pool_level and pump_running_watts table defs to pooldb.py
  so that you do not have to modify table definitions in main script.
- Added in temperature compensation function for pH readings if you
  have a pool water temp probe. Configuration is done in pooldb.py

<br>

V3.0 (2016-09-04)
- Added additional relay to control sprinkler transformer so it is not running 24x7.
- Added new function to control both relays. 
- Added addition debug and logging messages.
<br>
V3.1 (2016-10-08)
- Added new sensor checking function to check that our temp and
  pool level sensors are responding as required and included
  notifications if they exceed a certain number of timeouts
  or their battery voltage drops too low. Also updated pool
  fill to stop automatically if we lose communication with 
  with our pool level sensor.

- Updated pool_fill() to include calls to differnt functions
  to streamline that particular function. Also cuts down on
  a couple of global variables. Need to continue to clean
  this up as I go through and optimize the code. 

- Changed the way we get the pool level. We used to have a 0
  or a 1 programmed to be sent directly from the sensor. We
  would then make a decision to fill the pool based on the 
  reading from the sensor. Now I output the actual resistance
  from the sensor to the database and using these values we 
  can change the level of when we want to fill the pool 
  within pooldb.py instead of having to physically reflash
  the pool_level arduino sensor.
  
  
<br>

V3.2 (Unpublished)

<br>

V3.3.03.01 (2018-02-22)
- Major rewrite of code. Instead of a very large, nearly monolithic threaded
  application, I rewrote the code into various parts. The first part is a
  threaded application that does nothing more than to watch for physical
  button presses on the pool control console and does an action based on what
  button has been pressed. The second part is a cron based application that
  does all of the sensor checking and data gathering and fills the pool when
  necessary.
  
- Flask web frontend (V1) completed. Basic implementation of a Flask framework
  and web frontend that allows viewing of all of the pool parameters like
  temperature, pool water level, pH, Orp, pump watts in use, battery conditions
  for the various sensors and more. It also allows for the manual filling of the
  pool as well as the stopping of an automatic fill that is already running.
  Includes ability to toggle all notifications (email, sms & pushbullet) as well
  as debug and logging setting via the web interface.
  
- Added Acid level sensor and associated functions to watch the acid level in tank
  and notify us when the acid level get too low.
  
- Added email and twilio (SMS) notifications to pushbullet. Requires (free) pushbullet
  an/or paid Twilio account. 
  
  <br>
  
V3.3.05 (2018-02-27)
- Added pump control of Pentair Intelliflo VF pump. MAJOR thanks to Russell Goldin
  (russ.goldin@gmail.com) for his amazing work on the Pentair RS-485 control software 
  needed for my system to be able to talk to and control my pump. You can check out his github
  [HERE](https://github.com/tagyoureit/nodejs-poolController/tree/4.x-DEV).
- Updated templates/index.html to add pump status and controls to web interface
- Updated main code to include start/stop and system checks for pump control
- Added ability to start and stop pump control software from web interface.
- Added House Main power watts, total watts in use and Solar production to web interface.
Eventually this will allow me to control my pump based on solar output instead of just ON & OFF.
- Minor logging and bug fixes

<br>

V3.4 (2018-03-16)
- Started the process to pull functions into their own modules. Started with get_ph.py and get_orp.py but will be doing more of this as I move forward just to clean up the code and separate out various functions.
- Built in the ability to toggle (via the web interface) notifications based on various systems (pump control, fill, DB errors, time outs, etc) so that you can fine tune the types of notifications that you get on a regular basis.
- Rewrote the get_ph and get_orp functions to clean up serial utilization and take care of some weird data errors. Also they can be called as standalone scripts or via the main pool_control_master.py. 
- Rewrote temperature correction for pH and now allow pH recording less temperature correction if there is no water temp probe on the system. This will result in slightly inaccurate pH, but it is better than nothing.
- Updated web interface to add pH and ORP active gauges.
- Updated web interface Pump GPM so that if the pump control is offline the gauge will now read "0" instead of "31" which is what the pump reports even thought is is off. 
- Cleaned up the code in the web interface. Still more to do here.
 
<br>

V3.4.6 (2018-09-23)
- Rewrote all notification functions including logging, debug, sms, email, and pushbullet. (notifications.py)
- Integrated InfluxDB for reading and writing various temperature, power and pH/Orp data points.
- Added ability to toggle automatic pool fill function via the web interface.
- Added pool pH and ORP graphs to bottom of web interface via Grafana and InfluxDB.
- Continued code cleanup as I learn more about python and better ways of doing things!

<br>

Based on the following hardware:

-Raspberry Pi 3<br>
-LowPowerLabs MightyHat (http://lowpowerlab.com/mightyhat)<br>
-eTape Resistive Liquid Measuring tape (http://www.milonetech.com)<br>
-OpenEnergyMonitor emonTH & emonPi (http://www.openenergymonitor.org)<br>
-Atlas Scientific USB based pH and ORP probes (http://www.atlas-scientific.com)<br>
-DFRobot Liquid Level Sensor (Acid Level Monitoring) (http://www.dfrobot.com)

## Authors

* **Richard J. Sears** - *richard@sears.net* - [The RS Technical Group, Inc.](http://github.com/rjsears)

## License

This project is licensed under the MIT License - see the MIT License for details

## Acknowledgments

* [Gerrit Grunwald, Mark Crossley](https://github.com/HanSolo/SteelSeries-Canvas) - Steel Series Gauges
* [Randomchars](https://github.com/randomchars) - pushbullet.py
* [Russell Goldin](https://github.com/tagyoureit/nodejs-poolController/tree/4.x-DEV) - Pentair Control Code
* My amazing family that puts up with all of my coding projects!
