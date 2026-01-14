import RPi.GPIO as GPIO
import adafruit_dht
import time
import datetime
import board
import logging
import sys
from w1thermsensor import W1ThermSensor, Unit

# 0 indicates active relay
# 1 indicates inactive relay

class IceMaker():
    relays = {
        # water pump to fill the resevoir
        'water_valve': 12,
        # melts the ice from the plate
        'hot_gas_solenoid': 5,
        # builds ice on the plate
        'recirculating_pump': 6,
        # main compressor, reverse relay cannot active when compressors are ON
            # needs to be tuned into function
        'compressor_1': 24,
        # main compressor, reverse relay cannot active when compressors are ON
            # needs to be tuned into function
        'compressor_2': 25,
        # Needs to be on when running an ice making cycle
            # when the compressor is on and the reverse relay is off (ice making cylce)
        'condenser_fan': 23,
        # LED light for status of ice machine
        'LED': 22,
        # Ice Cutter
        'ice_cutter': 27
    }
    
    relay_names = {
        # water pump to fill the resevoir
        'water_valve': 'Water Valve',
        # melts the ice from the plate
        'hot_gas_solenoid': 'Hot Gas Solenoid',
        # builds ice on the plate
        'recirculating_pump': 'Recirculating Pump',
        # main compressor, reverse relay cannot active when compressors are ON
            # needs to be tuned into function
        'compressor_1': 'Compressor 1',
        # main compressor, reverse relay cannot active when compressors are ON
            # needs to be tuned into function
        'compressor_2': 'Compressor 2',
        # Needs to be on when running an ice making cycle
            # when the compressor is on and the reverse relay is off (ice making cylce)
        'condenser_fan': 'Condenser Fan',
        # LED light for status of ice machine
        'LED': 'LED',
        # Ice Cutter
        'ice_cutter': 'Ice Cutter'
    }

    #sensors = {
    #     # Whole machine temperature and humidity sensor
    #    'temp_humidity_sensor': 17
    #}

    # fill counters
    fill_count = 0
    total_fill_count = 0
    last_batch = None
    MIN=60

    def __init__(self):
        #self.MIN = 2 if self.debug else 60
        logging.basicConfig(stream=sys.stdout, 
                level=logging.DEBUG,
                format='%(asctime)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S')
        self.logger = logging.getLogger()
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        for relay in self.relays.values():
            GPIO.setup(relay, GPIO.OUT, initial=GPIO.HIGH)
            GPIO.output(relay, 1)
        
        # Setup 1-Wire temp sensors
        self.ice_bin_temp_sensor_id = "3c01f0956abd"
        self.plate_temp_sensor_id = "092101487373"
        self.ice_bin_temp_sensor = W1ThermSensor(sensor_id=self.ice_bin_temp_sensor_id)
        self.plate_temp_sensor = W1ThermSensor(sensor_id=self.plate_temp_sensor_id)
        
        self.mode = 'IDLE'
        self.system_start_time = time.monotonic()
        self.mode_start_time = self.system_start_time
        self.time_in_mode = 0
        self.cycle_start_time = self.system_start_time
        self.time_in_cycle = 0
        self.cycle_finish_time = self.system_start_time
        self.bin_temp = 100
        self.plate_temp = 100
        self.plate_target = 32
        self.cycle_count = 0
        # add config params here (to be overwritten by those read in from config file later)
        # ... TBD

    def sensor_check(self):
        try:
            #ambient_th_sensor = adafruit_dht.DHT22(board.D17, False)
            #ice_bucket_temp = W1ThermSensor()

            #temperature_c = ambient_th_sensor.temperature
            #temperature_f = temperature_c * (9 / 5) + 32
            #humidity = ambient_th_sensor.humidity
            ice_bucket_temperature = ice_bucket_temp.get_temperature()
            ice_bucket_temperature_f = ice_bucket_temperature * (9 / 5) + 32
            #print("Temp={0:0.1f}ºC, Temp={1:0.1f}ºF, Humidity={2:0.1f}%, Temp={3:0.1f}ºF".format(temperature_c, temperature_f, humidity, ice_bucket_temperature))
            self.logger.info("Ice Bucket Temp={0:0.1f}ºF".format(ice_bucket_temperature_f))
            return ice_bucket_temperature_f
        except RuntimeError as error:
            # Errors happen fairly often, DHT's are hard to read, just keep going
            print(error.args[0])
            return None
        except Exception as error:
            ambient_th_sensor.exit()
            return None

    def power_off(self):
        for relay in self.relays.keys():
            print(relay)
            self.relay_off(relay)
        self.logger.warning('Powered off all relays.')

    def power_on(self):
        #start up only, aka only one run once on first boot
        self.logger.info('\tActivating Power On Startup Sequence')

        # turn on the water valve for 2 minutes
        duration = 1
        self.logger.info(f'\t\tTurning on water valve for {duration} min.')
        self.relay_on('water_valve')
        time.sleep(duration * self.MIN)
        # turn off the water valve
        self.logger.info('\t\tTurning off water valve')
        self.relay_off('water_valve')

        # turn on the recirculating pump for 1 minute
        duration = 0.25
        self.logger.info(f'\t\tTurning on recirculating pump for {duration} min.')
        self.relay_on('recirculating_pump')
        time.sleep(duration * self.MIN)
        # turn off the recirculating pump 
        self.logger.info('\t\tTurning off recirculating pump')
        self.relay_off('recirculating_pump')

        # turn on the water valve for 2 minutes
        duration = 0.25
        self.logger.info(f'\t\tTurning on water valve for another {duration} min.')
        self.relay_on('water_valve')
        time.sleep(duration * self.MIN)
        # turn off the water valve
        self.logger.info('\t\tTurning off water valve')
        self.relay_off('water_valve')

        #completion of power on sequence
        self.logger.info('\tCompletion of Power On Sequence')  
    
    def log_data(self):
        self.logger.debug(self.mode + f' {self.plate_target} {self.plate_temp:.02f} {self.bin_temp:.02f} {int(self.time_in_mode/self.MIN):02d}:{round(self.time_in_mode % self.MIN):02d} {int(self.time_in_cycle/self.MIN):02d}:{round(self.time_in_cycle % self.MIN):02d}')
        
    def chill_plate(self, timeout=25*60, target_temp=25, recirc=False):
        self.logger.info(f'\tChilling Plate to {target_temp} °F, Recirculation ' + ('On' if recirc else 'Off'))
        self.plate_temp = self.plate_temp_sensor.get_temperature(Unit.DEGREES_F)
        self.bin_temp = self.ice_bin_temp_sensor.get_temperature(Unit.DEGREES_F)
        self.mode_start_time = time.monotonic()
        self.plate_target = target_temp
        chilling = True if (self.plate_temp > target_temp) else False # Only turn compressor etc on if temp is above target temp
        if chilling:
            # hot gas/water fill OFF
            self.relay_off('hot_gas_solenoid', True)
            self.relay_off('water_valve', True)
            # condenser/compressor ON
            self.relay_on('condenser_fan', True)
            self.relay_on('compressor_1', True)
            self.relay_on('compressor_2', True)
            # recirculating pump
            if recirc:
                self.relay_on('recirculating_pump', True)
            else:
                self.relay_off('recirculating_pump', True)
        else:
            self.logger.info(f'\tSkipping Chilling Sequence.  Plate temp ({self.plate_temp} °F) is below target temp ({target_temp} °F).')
        
        wait_time = self.MIN / 12.0
        while chilling:
            self.time_in_mode = time.monotonic() - self.mode_start_time
            self.time_in_cycle = time.monotonic() - self.cycle_start_time
            self.plate_temp = self.plate_temp_sensor.get_temperature(Unit.DEGREES_F) 
            self.bin_temp = self.ice_bin_temp_sensor.get_temperature(Unit.DEGREES_F)

            if self.time_in_mode > timeout: # Check for timeout
                chilling = False
                self.logger.info(f'\tChilling Timed out after {timeout/self.MIN:.02f} minutes.  Ending Chilling Sequence.')
            elif self.plate_temp > target_temp:  # Continue Chilling Plate if still above target temp
                # wait for plate temp to reach > 52 degrees F
                #self.logger.info(f'Target: {target_temp} °F. Current Temp: {temp:.2f} °F Plate, {bin_temp:.2f} °F Bin.  Time spent: {time_spent/60:.02f} minutes')
                self.log_data()
                time.sleep(max(0, (wait_time - ((time.monotonic() - self.mode_start_time) - self.time_in_mode))))
            else:  # stop if reached target temp
                self.log_data()
                self.logger.info(f'\t\tCurrent Temp: {self.plate_temp:.2f} °F.  Reached chilling target ({target_temp} °F)!')
                chilling = False
                self.logger.info('\tEnding Chilling Sequence')
        #  Condenser fan & compressor are left ON.  Main loop decides what to do based on ice bin fullness (proceed to ice making or go to sleep)
              
        
    def ice_making(self, ice_target_temp = 6.5):
        #Start ice making sequence
        self.logger.info('\tActivating Ice Making Sequence')

        # PRECHILL ICE PLATE
        #self.chill_plate(timeout= 2*self.MIN)
        
        
        # Ice-making phase
        self.logger.info('\t\tStarting Ice Making Process')
        self.chill_plate(target_temp=ice_target_temp, recirc=True, timeout=25*self.MIN)
        self.logger.info('\t\tCompleting Ice Making Process')
        # Finish Ice-Making Phase
        #   Turn off condenser fan & recirc pump, but leave compressor on (for harvest)
        self.relay_off('condenser_fan',True)
        self.relay_off('recirculating_pump',True)
        self.last_batch = time.monotonic()
        self.logger.info('\tCompleting Ice Making Sequence')

    def harvest(self, timeout = 4*60, harvest_threshold = 52.5):
        self.mode_start_time = time.monotonic()
        self.logger.info(f'\Activating Harvest Sequence.  Target temp: {harvest_threshold} °F')
        self.plate_target = harvest_threshold
        #Start harvest sequence
        # ensure condenser fan & recirc pump are off
        self.relay_off('condenser_fan')
        self.relay_off('recirculating_pump')
        
        # start harvest
        self.relay_on('water_valve', True)  # Fill water reservoir while harvesting
        self.relay_on('hot_gas_solenoid', True) # Configure to heat the plate
        self.relay_on('ice_cutter') # Turn on ice cutter
        harvesting = True
        wait_time = self.MIN / 12
        while harvesting:
            self.time_in_mode = time.monotonic() - self.mode_start_time
            self.time_in_cycle = time.monotonic() - self.cycle_start_time
            self.plate_temp = self.plate_temp_sensor.get_temperature(Unit.DEGREES_F)
            self.bin_temp = self.ice_bin_temp_sensor.get_temperature(Unit.DEGREES_F)
            if (time.monotonic() - self.mode_start_time) > timeout: # Check for timeout
                harvesting = False
                self.logger.info(f'\tHarvest Timed out after {timeout/60} minutes')
            elif self.plate_temp < harvest_threshold:
                # wait for plate temp to reach > 52 degrees F
                #self.logger.info(f'\tWaiting  ({wait_time} more seconds) for plate to warm up to {harvest_threshold} °F. Current Temp: {self.plate_temp:.2f} °F')
                self.log_data()
                time.sleep(wait_time)
            else:
                self.log_data()
                self.logger.info(f'\tCurrent Temp: {self.plate_temp:.2f} °F.  Reached harvest threshold ({harvest_threshold} °F)!')
                harvesting = False

            # end harvest
        self.logger.info('\tEnding Harvest Sequence')
        self.relay_off('hot_gas_solenoid', True)
        self.relay_off('water_valve', True)
        # leave compressor on (prep for cooling off the plate), turn on condenser fan
        self.relay_on('condenser_fan', True)

    def test_relay(self, relay, duration):
        self.logger.info('\tRelay Test')
        self.relay_on(relay, True)
        time.sleep(duration)
        self.relay_off(relay, True)

    def relay_on(self, relay, log = False):
        if log:
            self.logger.info(f'\t\tTurning ON {self.relay_names[relay]}')
        GPIO.output(self.relays[relay], 0)

    def relay_off(self, relay, log = False):
        if log:
            self.logger.info(f'\t\tTurning OFF {self.relay_names[relay]}')
        GPIO.output(self.relays[relay], 1)
    def bin_full(self, threshold=35):
        self.bin_temp = self.ice_bin_temp_sensor.get_temperature(Unit.DEGREES_F)
        self.logger.info(f'Bucket temp: {self.bin_temp:.2f} °F.')
        return (self.bin_temp < threshold)
        
if __name__ == '__main__':
    ice_maker = IceMaker()
    ice_maker.debug = False
    ice_maker.MIN = 60
    
    # Debug Only ------------------
    if ice_maker.debug:
        ice_maker.MIN = 1
        # walk through relays 1 at a time
        test_time = 1 #seconds
        for relay in ['water_valve', 'condenser_fan', 'recirculating_pump', 'hot_gas_solenoid', 'ice_cutter']:
            ice_maker.test_relay(relay, test_time)
        # Turn on/off compressor_1 & _2 together
        ice_maker.relay_on('compressor_1', True)
        ice_maker.relay_on('compressor_2', True)
        time.sleep(test_time)
        ice_maker.relay_off('compressor_1', True)
        ice_maker.relay_off('compressor_2', True)
    # -----------------------------       
    
    
    
    try:
        for sensor in W1ThermSensor.get_available_sensors():
            ice_maker.logger.info("Sensor %s has temperature %.2f deg F" % (sensor.id, sensor.get_temperature(Unit.DEGREES_F)))
    except:
        ice_maker.logger.error('Error reading temperature sensor on startup.')
    

    # Read from file:
       # long term data like \
           # total number of batches made
           # compressor turn ons (count)
           # compressor turn on time
           # compressor cooling time
           # compressor heating time
           # hot gas solenoid activations (while compressor on)
           # door open count
           # door open duration
       # config settings
           # rechill temp/timeout
           # ice-making temp/timeout
           # harvest temp/timout
           # bin-full threshold
           
       
    
    ice_maker.logger.info('Powering On...')
    try:
        ice_maker.power_on()
        #print(lamp)
        while True:
            ice_maker.relay_on('ice_cutter') # Turn on ice cutter
            
            ice_maker.cycle_start_time = time.monotonic()
            ice_maker.mode = 'CHILL'
            ice_maker.chill_plate(timeout=2*ice_maker.MIN, target_temp=32)  #     Prechill
            ice_maker.mode = 'ICE'
            ice_maker.ice_making(ice_target_temp=-2) #                            Make Ice
            ice_maker.mode = 'HEAT'
            ice_maker.harvest(timeout=4*ice_maker.MIN, harvest_threshold=38) #    Harvest
            ice_maker.mode = 'CHILL'
            ice_maker.chill_plate(timeout=5*ice_maker.MIN, target_temp=35) #      Rechill
            ice_maker.cycle_finish_time = time.monotonic()
            ice_maker.cycle_count += 1
            ice_maker.logger.info(f'Cycle Count: {ice_maker.cycle_count}')
            while ice_maker.bin_full(threshold=35):
                ice_maker.logger.info(f'Ice bin full...sleeping.')
                time.sleep(1 * ice_maker.MIN)
                if time.monotonic() > (ice_maker.cycle_finish_time + 15*ice_maker.MIN):
                    ice_maker.relay_off('ice_cutter')
                
                ice_maker.bin_temp = ice_maker.ice_bin_temp_sensor.get_temperature(Unit.DEGREES_F)
                min_bin_temp = 33
                max_time_after_cycle_finish = 20
                # if bin temp gets below threshold, or enough time passes after the cycle finish time, shut off the compressor            
                if ice_maker.bin_temp < min_bin_temp: 
                    ice_maker.logger.info(f'Ice Bin Full and Bin Temp is below {min_bin_temp} °F ({ice_maker.bin_temp:.02f} °F), turning off compressor & fan.')
                    ice_maker.mode = 'IDLE'
                    ice_maker.relay_off('compressor_1', True)
                    ice_maker.relay_off('compressor_2', True)
                    ice_maker.relay_off('condenser_fan', True)
                elif time.monotonic() > (ice_maker.cycle_finish_time + max_time_after_cycle_finish*ice_maker.MIN):
                    ice_maker.logger.info(f'Ice Bin Full and {max_time_after_cycle_finish} minutes passed, turning off compressor & fan.')
                    ice_maker.mode = 'IDLE'
                    ice_maker.relay_off('compressor_1', True)
                    ice_maker.relay_off('compressor_2', True)
                    ice_maker.relay_off('condenser_fan', True)
                    
            ice_maker.logger.info(f'Ice Bin not full...restarting ice-making cycle.')
            
            # periodically write long term stats to file

    except Exception as error:
        ice_maker.power_off()
        ice_maker.logger.warning('SYSTEM POWER OFF, TURNING OFF ALL RELAYS...')
        # log all long term data stuff to file
        ice_maker.logger.warning('An error occurred...' + str(error))
        
    except:
        ice_maker.logger.warning('SYSTEM POWER OFF, TURNING OFF ALL RELAYS...')
        ice_maker.power_off()