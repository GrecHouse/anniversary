"""
Anniversary sensor supporting the lunar calendar.
For more details about this platform, please refer to the documentation at
https://github.com/GrecHouse/anniversary

* korean-lunar-calendar 라이브러리를 이용합니다.
에러가 발생할 경우 pip 로 설치해주세요.
https://pypi.org/project/korean-lunar-calendar/

HA 기념일 센서 : 기념일의 D-Day 정보와 양/음력 정보를 알려줍니다.
다모아님의 아이디어를 기반으로 제작되었습니다.
"""

from datetime import timedelta, date, datetime
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.sensor import ENTITY_ID_FORMAT, PLATFORM_SCHEMA
from homeassistant.const import CONF_SENSORS, CONF_NAME, CONF_TYPE, ATTR_DATE
from homeassistant.helpers.entity import Entity, async_generate_entity_id
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.util.json import load_json
from homeassistant.helpers.event import async_track_point_in_utc_time
from korean_lunar_calendar import KoreanLunarCalendar

_LOGGER = logging.getLogger(__name__)

CONF_IS_LUNAR_DATE = 'lunar'
CONF_INTERCALATION = 'intercalation'
CONF_TTS_DAYS = 'tts_days'
CONF_TTS_SCAN_INTERVAL = 'tts_scan_interval'

TTS = {}
INTERCALATION = ' (윤달)'
PERSISTENCE = '.shopping_list.json'

SENSOR_SCHEMA = vol.Schema({
    vol.Required(ATTR_DATE): cv.string,
    vol.Optional(CONF_NAME, default=''): cv.string,
    vol.Optional(CONF_TYPE, default='anniversary'): cv.string,
    vol.Optional(CONF_IS_LUNAR_DATE, default=False): cv.boolean,
    vol.Optional(CONF_INTERCALATION, default=False): cv.boolean,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SENSORS): cv.schema_with_slug_keys(SENSOR_SCHEMA),
    vol.Optional(CONF_TTS_DAYS, default=3): cv.positive_int,
    vol.Optional(CONF_TTS_SCAN_INTERVAL, default=86460): cv.positive_int,
})


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Anniversary sensor."""
    if hass.config.time_zone is None:
        _LOGGER.error("Timezone is not set in Home Assistant configuration")
        return False

    sensors = []

    for device, device_config in config[CONF_SENSORS].items():
        date_str = device_config.get(ATTR_DATE)
        is_lunar = device_config.get(CONF_IS_LUNAR_DATE)
        is_intercalation = device_config.get(CONF_INTERCALATION)
        anniv_type = device_config.get(CONF_TYPE)

        name = device_config.get(CONF_NAME)
        if name == '':
            name = device

        is_mmdd = False
        if dt_util.parse_date(date_str) is None:
            year_added_date_str = str(dt_util.as_local(dt_util.utcnow()).date().year) + "-" + date_str
            if dt_util.parse_date(year_added_date_str) is not None:
                date_str = year_added_date_str
                is_mmdd = True
            else:
                continue

        sensor = AnniversarySensor(hass, device, name, date_str, is_lunar, is_intercalation, anniv_type, is_mmdd)
        async_track_point_in_utc_time(
            hass, sensor.point_in_time_listener, sensor.get_next_interval())

        sensors.append(sensor)

    sensor = AnniversaryTTSSensor(hass, "anniversary_tts", config.get(CONF_TTS_DAYS), config.get(CONF_TTS_SCAN_INTERVAL))
    async_track_point_in_utc_time(
            hass, sensor.point_in_time_listener, sensor.get_next_interval())
    sensors.append(sensor)

    async_add_entities(sensors, True)


class AnniversaryTTSSensor(Entity):
    """Implementation of a Anniversary TTS sensor."""
    def __init__(self, hass, name, tts_days, tts_scan_interval):
        self._name = name
        self._state = ''
        self._tts_days = tts_days
        self._tts_scan_interval = tts_scan_interval
        self.hass = hass
        self._update_internal_state(dt_util.utcnow())

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return 'mdi:text-to-speech'
    
    @property
    def device_state_attributes(self):
        """Return the attribute(s) of the sensor"""
        return self._attribute

    def solar_to_lunar(self, solarDate):
        calendar = KoreanLunarCalendar()
        calendar.setSolarDate(solarDate.year, solarDate.month, solarDate.day)
        lunar = calendar.LunarIsoFormat()
        lunar = lunar.replace(' Intercalation', INTERCALATION)
        return lunar

    def lunar_to_solar(self, lunarDate, intercal):
        calendar = KoreanLunarCalendar()
        calendar.setLunarDate(lunarDate.year, lunarDate.month, lunarDate.day, intercal)
        return dt_util.parse_date(calendar.SolarIsoFormat())

    def _update_internal_state(self, time_date):
        
        shopping_list = load_json(self.hass.config.path(PERSISTENCE), default=[])

        todo_list = {}
        tts_add_list = {}

        keys = {}
        def rename(todo_name):
            if todo_name in keys:
                keys[todo_name] += 1
                return ''.join([todo_name,'(',str(keys[todo_name]),')'])
            else:
                keys[todo_name] = 1
                return todo_name
        
        for item in shopping_list:
            if not item['complete']:
                if item['name'].startswith('양') or item['name'].startswith('음'):
                    isLunar = item['name'].startswith('음')

                    try:
                        todo_date = item['name'][1:5]
                        todo_name = item['name'][6:]
                        solar_date = ''
                        ldate = ''
                        intercal = False
                        
                        adddate = dt_util.parse_date(str(datetime.now().year) + '-' + todo_date[0:2] + '-' + todo_date[2:])
                        adddate_early = dt_util.parse_date(str(datetime.now().year-1) + '-' + todo_date[0:2] + '-' + todo_date[2:])

                        if isLunar:
                            intercal = '(윤)' in todo_name
                            solar_date = self.lunar_to_solar(adddate_early, intercal)
                            if solar_date < datetime.now().date():
                                solar_date = self.lunar_to_solar(adddate, intercal)
                            ldate = str(adddate.month) + "." + str(adddate.day)
                            if intercal:
                                ldate = ldate + INTERCALATION
                                todo_name = todo_name.replace('(윤)','')
                        else:
                            solar_date = adddate
                        
                        if solar_date < datetime.now().date():
                            solar_date = dt_util.parse_date(str(datetime.now().year+1) + '-' + todo_date[0:2] + '-' + todo_date[2:])
                            if isLunar:
                                solar_date = self.lunar_to_solar(solar_date, intercal)

                        dday = (solar_date - datetime.now().date()).days
                        sdate = str(solar_date.month) + "." + str(solar_date.day)
                        
                        todo_rename = rename(todo_name)

                        if dday < self._tts_days + 1:
                            tts_add_list[todo_rename] = dday

                        if isLunar:
                            todo_list[todo_rename] = [dday, sdate, ldate, todo_name]
                        else:
                            todo_list[todo_rename] = [dday, sdate, "solar", todo_name]

                    except:
                        _LOGGER.warn("Not date : %s", item['name'])
                        pass

        self._attribute = todo_list

        tts_add_list.update(TTS)

        anniv_list = sorted(tts_add_list.items(), key=(lambda x: x[1]))
        msg = ''
        for anniv in anniv_list:
            name = anniv[0]
            value = anniv[1]
            if value < self._tts_days + 1:
                if todo_list.get(name) is not None:
                    name = todo_list.get(name)[3]
                if msg != '':
                    msg = msg + ", "
                if value == 0:
                    msg = msg + " ".join(["오늘은", name])
                elif value == 1:
                    msg = msg + " ".join(["내일은", name])
                else:
                    msg = msg + " ".join([str(value)+"일 후는", name])
        self._state = msg

    def get_next_interval(self, now=None):
        """Compute next time an update should occur."""
        interval = self._tts_scan_interval

        if now is None:
            now = dt_util.utcnow()
        if interval == 86460 or interval is None:
            now = dt_util.start_of_local_day(dt_util.as_local(now))
        return now + timedelta(seconds=interval)

    @callback
    def point_in_time_listener(self, time_date):
        """Get the latest data and update state."""
        self._update_internal_state(time_date)
        self.async_schedule_update_ha_state()
        async_track_point_in_utc_time(
            self.hass, self.point_in_time_listener, self.get_next_interval())


class AnniversarySensor(Entity):
    """Implementation of a Anniversary sensor."""

    def __init__(self, hass, deviceId, name, dateStr, lunar, intercalation, aType, mmdd):
        """Initialize the sensor."""
        self.entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, deviceId, hass=hass)
        self._name = name
        self._date = dt_util.parse_date(dateStr)
        self._lunar = lunar
        self._intercalation = intercalation
        self._type = aType
        self._mmdd = mmdd
        self._state = None
        self.hass = hass
        self._update_internal_state(dt_util.utcnow())

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if self._type == 'birth':
            return 'mdi:calendar-star'
        elif self._type == 'wedding':
            return 'mdi:calendar-heart'
        elif self._type == 'memorial':
            return 'mdi:calendar-clock'
        else:
            return 'mdi:calendar-check'

    @property
    def device_state_attributes(self):
        """Return the attribute(s) of the sensor"""
        return self._attribute

    def solar_to_lunar(self, solarDate):
        calendar = KoreanLunarCalendar()
        calendar.setSolarDate(solarDate.year, solarDate.month, solarDate.day)
        lunar = calendar.LunarIsoFormat()
        lunar = lunar.replace(' Intercalation', INTERCALATION)
        return lunar

    def lunar_to_solar(self, today, thisYear):
        lunarDate = self._date
        calendar = KoreanLunarCalendar()
        if thisYear or self._mmdd:
            calendar.setLunarDate(today.year, lunarDate.month, lunarDate.day, self._intercalation)
            if calendar.SolarIsoFormat() == '0000-00-00':
                lunarDate2 = lunarDate - timedelta(1)
                calendar.setLunarDate(today.year, lunarDate2.month, lunarDate2.day, self._intercalation)
                _LOGGER.warn("Non-existent date correction : %s -> %s", lunarDate, calendar.SolarIsoFormat())
        else:
            calendar.setLunarDate(lunarDate.year, lunarDate.month, lunarDate.day, self._intercalation)
        return dt_util.parse_date(calendar.SolarIsoFormat())

    def lunar_to_solar_early_day(self, today):
        lunarDate = self._date
        calendar = KoreanLunarCalendar()
        calendar.setLunarDate(today.year-1, lunarDate.month, lunarDate.day, self._intercalation)
        if calendar.SolarIsoFormat() == '0000-00-00':
            lunarDate2 = lunarDate - timedelta(1)
            calendar.setLunarDate(today.year-1, lunarDate2.month, lunarDate2.day, self._intercalation)
            _LOGGER.warn("Non-existent date correction : %s -> %s", lunarDate, calendar.SolarIsoFormat())
        return dt_util.parse_date(calendar.SolarIsoFormat())

    def lunar_gapja(self, lunarDate):
        intercalation = False
        if '윤달' in lunarDate:
            intercalation = True
            lunarDate = lunarDate.replace(INTERCALATION,'')
        calendar = KoreanLunarCalendar()
        try:
            lunar = dt_util.parse_date(lunarDate)
            calendar.setLunarDate(lunar.year, lunar.month, lunar.day, intercalation)
        except AttributeError: 
            try:
                calendar.setLunarDate(lunarDate[:4], lunarDate[5:7], lunarDate[8:], intercalation)
            except:
                return "-"
        return calendar.getGapJaString()

    def is_past(self, today):
        anniv = self._date
        if self._lunar:
            anniv = self.lunar_to_solar(today, True)
        else:
            anniv = date(today.year, anniv.month, anniv.day)
        if (anniv-today).days < 0:
            return True
        else:
            return False

    def past_days(self, today):
        anniv = self._date
        if self._lunar:
            anniv = self.lunar_to_solar(today, False)
        delta = today - anniv
        return delta.days + 1

    def korean_age(self, today, dday):
        addyear = 1 + dt_util.parse_date(dday).year - today.year
        return today.year - self._date.year + addyear

    def upcoming_count(self, today):
        anniv = self._date
        if self._lunar:
            anniv = self.lunar_to_solar(today, False)

        if self.is_past(today):
            return today.year - anniv.year + 1
        else:
            return today.year - anniv.year

    def d_day(self, today):
        anniv = self._date

        if self._lunar:
            anniv_early_day = self.lunar_to_solar_early_day(today)
            delta = anniv_early_day - today
            if delta.days >= 0:
                return [delta.days, anniv_early_day.strftime('%Y-%m-%d')]

        if self.is_past(today):
            if self._lunar:
                if today.month == 2 and today.day == 29:
                    newday = date(today.year+1, today.month, today.day-1)
                else:
                    newday = date(today.year+1, today.month, today.day)
                anniv = self.lunar_to_solar(newday, True)
            else:
                if anniv.month == 2 and anniv.day == 29:
                    anniv = date(today.year+1, anniv.month, anniv.day-1)
                else:
                    anniv = date(today.year+1, anniv.month, anniv.day)
        else:
            if self._lunar:
                anniv = self.lunar_to_solar(today, True)
            else:
                anniv = date(today.year, anniv.month, anniv.day)

        delta = anniv - today
        return [delta.days, anniv.strftime('%Y-%m-%d')]

    def get_next_interval(self, now=None):
        """Compute next time an update should occur."""
        if now is None:
            now = dt_util.utcnow()
        now = dt_util.start_of_local_day(dt_util.as_local(now))
        return now + timedelta(seconds=86400)

    def _update_internal_state(self, time_date):
        today = dt_util.as_local(dt_util.utcnow()).date()
        dday = self.d_day(today)
        self._state = dday[0]
        solar_date = self._date
        lunar_date = self._date.strftime('%Y-%m-%d')
        if self._intercalation:
            lunar_date = lunar_date + INTERCALATION
        if self._lunar:
            solar_date = self.lunar_to_solar(today, False)
        else:
            lunar_date = self.solar_to_lunar(self._date)

        self._attribute = { 
            'type': self._type,
            'solar_date': solar_date.strftime('%Y-%m-%d'),
            'lunar_date': lunar_date,
            'lunar_date_gapja': self.lunar_gapja(lunar_date),
            'past_days': '-' if self._mmdd else self.past_days(today),
            'upcoming_count': '-' if self._mmdd else self.upcoming_count(today),
            'upcoming_date': dday[1],
            'korean_age': '-' if self._mmdd or self._type != 'birth' else self.korean_age(today, dday[1]),
            'is_lunar': str(self._lunar),
            'is_mmdd': str(self._mmdd)
        }

        global TTS
        TTS[self._name] = self._state

    @callback
    def point_in_time_listener(self, time_date):
        """Get the latest data and update state."""
        self._update_internal_state(time_date)
        self.async_schedule_update_ha_state()
        async_track_point_in_utc_time(
            self.hass, self.point_in_time_listener, self.get_next_interval())
