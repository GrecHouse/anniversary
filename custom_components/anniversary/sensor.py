"""
Anniversary sensor supporting the lunar calendar.
For more details about this platform, please refer to the documentation at
https://github.com/GrecHouse/anniversary

* korean-lunar-calendar 라이브러리 소스를 이용합니다.
https://pypi.org/project/korean-lunar-calendar/
https://github.com/usingsky/korean_lunar_calendar_py

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

        sensor = AnniversarySensor(hass, device, name, date_str, is_lunar, is_intercalation, anniv_type)
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

                        if isLunar:
                            intercal = '(윤)' in todo_name
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

                        if dday < self._tts_days + 1:
                            tts_add_list[todo_name] = dday

                        if isLunar:
                            todo_list[todo_name] = [dday, sdate, ldate]
                        else:
                            todo_list[todo_name] = [dday, sdate, "solar"]

                    except ValueError:
                        _LOGGER.debug("Not date : %s", item['name'])

        self._attribute = todo_list

        tts_add_list.update(TTS)

        anniv_list = sorted(tts_add_list.items(), key=(lambda x: x[1]))
        msg = ''
        for anniv in anniv_list:
            key = anniv[0]
            value = anniv[1]
            if value < self._tts_days + 1:
                if msg != '':
                    msg = msg + ", "
                if value == 0:
                    msg = msg + " ".join(["오늘은", key])
                elif value == 1:
                    msg = msg + " ".join(["내일은", key])
                else:
                    msg = msg + " ".join([str(value)+"일 후는", key])
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

    def __init__(self, hass, deviceId, name, dateStr, lunar, intercalation, aType):
        """Initialize the sensor."""
        self.entity_id = async_generate_entity_id(ENTITY_ID_FORMAT, deviceId, hass=hass)
        self._name = name
        self._date = dt_util.parse_date(dateStr)
        self._lunar = lunar
        self._intercalation = intercalation
        self._type = aType
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
        if thisYear:
            calendar.setLunarDate(today.year, lunarDate.month, lunarDate.day, self._intercalation)
        else:
            calendar.setLunarDate(lunarDate.year, lunarDate.month, lunarDate.day, self._intercalation)
        return dt_util.parse_date(calendar.SolarIsoFormat())

    def lunar_gapja(self, lunarDate):
        intercalation = False
        if '윤달' in lunarDate:
            intercalation = True
            lunarDate = lunarDate.replace(INTERCALATION,'')
        lunar = dt_util.parse_date(lunarDate)
        calendar = KoreanLunarCalendar()
        calendar.setLunarDate(lunar.year, lunar.month, lunar.day, intercalation)
        return calendar.getGapJaString()

    def is_past(self, today):
        anniv = self._date
        if self._lunar:
            anniv = self.lunar_to_solar(today, True)
        else:
            anniv = date(today.year, anniv.month, anniv.day)
        if (today.month > anniv.month) or ((today.month == anniv.month) and (today.day>anniv.day)):
            return True
        else:
            return False

    def past_days(self, today):
        anniv = self._date
        if self._lunar:
            anniv = self.lunar_to_solar(today, False)
        delta = today - anniv
        return delta.days + 1

    def korean_age(self, today):
        return today.year - self._date.year + 1

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
            anniv = self.lunar_to_solar(today, True)
        else:
            anniv = date(today.year, anniv.month, anniv.day)

        if self.is_past(today):
            anniv = date(today.year+1, anniv.month, anniv.day)

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
            'past_days': self.past_days(today),
            'upcoming_count': self.upcoming_count(today),
            'upcoming_date': dday[1],
            'is_lunar': str(self._lunar)
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


"""
KoreanLunarCalendar
Here is a library to convert Korean lunar-calendar to Gregorian calendar.
Korean calendar and Chinese calendar is same lunar calendar but have different date.
This follow the KARI(Korea Astronomy and Space Science Institute)
@author : usingsky@gmail.com
"""
class KoreanLunarCalendar(object) :
    KOREAN_LUNAR_MIN_VALUE = 13910101
    KOREAN_LUNAR_MAX_VALUE = 20501118
    KOREAN_SOLAR_MIN_VALUE = 13910205
    KOREAN_SOLAR_MAX_VALUE = 20501231

    KOREAN_LUNAR_BASE_YEAR = 1391
    SOLAR_LUNAR_DAY_DIFF = 35

    LUNAR_SMALL_MONTH_DAY = 29
    LUNAR_BIG_MONTH_DAY = 30
    SOLAR_SMALL_YEAR_DAY = 365
    SOLAR_BIG_YEAR_DAY = 366

    SOLAR_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31, 29]
    KOREAN_CHEONGAN = [0xac11, 0xc744, 0xbcd1, 0xc815, 0xbb34, 0xae30, 0xacbd, 0xc2e0, 0xc784, 0xacc4]
    KOREAN_GANJI = [0xc790, 0xcd95, 0xc778, 0xbb18, 0xc9c4, 0xc0ac, 0xc624, 0xbbf8, 0xc2e0, 0xc720, 0xc220, 0xd574]
    KOREAN_GAPJA_UNIT = [0xb144, 0xc6d4, 0xc77c]

    CHINESE_CHEONGAN = [0x7532, 0x4e59, 0x4e19, 0x4e01, 0x620a, 0x5df1, 0x5e9a, 0x8f9b, 0x58ec, 0x7678]
    CHINESE_GANJI = [0x5b50, 0x4e11, 0x5bc5, 0x536f, 0x8fb0, 0x5df3, 0x5348, 0x672a, 0x7533, 0x9149, 0x620c, 0x4ea5]
    CHINESE_GAPJA_UNIT = [0x5e74, 0x6708, 0x65e5]

    INTERCALATION_STR = [0xc724, 0x958f]

    KOREAN_LUNAR_DATA = [
            0x82c40653, 0xc301c6a9, 0x82c405aa, 0x82c60ab5, 0x830092bd, 0xc2c402b6, 0x82c60c37, 0x82fe552e, 0x82c40c96, 0xc2c60e4b,
            0x82fe3752, 0x82c60daa, 0x8301b5b4, 0xc2c6056d, 0x82c402ae, 0x83007a3d, 0x82c40a2d, 0xc2c40d15, 0x83004d95, 0x82c40b52,
            0x8300cb69, 0xc2c60ada, 0x82c6055d, 0x8301925b, 0x82c4045b, 0xc2c40a2b, 0x83005aab, 0x82c40a95, 0x82c40b52, 0xc3001eaa,
            0x82c60ab6, 0x8300c55b, 0x82c604b7, 0xc2c40457, 0x83007537, 0x82c4052b, 0x82c40695, 0xc3014695, 0x82c405aa, 0x8300c9b5,
            0x82c60a6e, 0xc2c404ae, 0x83008a5e, 0x82c40a56, 0x82c40d2a, 0xc3006eaa, 0x82c60d55, 0x82c4056a, 0x8301295a, 0xc2c6095e,
            0x8300b4af, 0x82c4049b, 0x82c40a4d, 0xc3007d2e, 0x82c40b2a, 0x82c60b55, 0x830045d5, 0xc2c402da, 0x82c6095b, 0x83011157,
            0x82c4049b, 0xc3009a4f, 0x82c4064b, 0x82c406a9, 0x83006aea, 0xc2c606b5, 0x82c402b6, 0x83002aae, 0x82c60937, 0xc2ffb496,
            0x82c40c96, 0x82c60e4b, 0x82fe76b2, 0xc2c60daa, 0x82c605ad, 0x8300336d, 0x82c4026e, 0xc2c4092e, 0x83002d2d, 0x82c40c95,
            0x83009d4d, 0xc2c40b4a, 0x82c60b69, 0x8301655a, 0x82c6055b, 0xc2c4025d, 0x83002a5b, 0x82c4092b, 0x8300aa97, 0xc2c40695,
            0x82c4074a, 0x83008b5a, 0x82c60ab6, 0xc2c6053b, 0x830042b7, 0x82c40257, 0x82c4052b, 0xc3001d2b, 0x82c40695, 0x830096ad,
            0x82c405aa, 0xc2c60ab5, 0x830054ed, 0x82c404ae, 0x82c60a57, 0xc2ff344e, 0x82c40d2a, 0x8301bd94, 0x82c60b55, 0xc2c4056a,
            0x8300797a, 0x82c6095d, 0x82c404ae, 0xc3004a9b, 0x82c40a4d, 0x82c40d25, 0x83011aaa, 0xc2c60b55, 0x8300956d, 0x82c402da,
            0x82c6095b, 0xc30054b7, 0x82c40497, 0x82c40a4b, 0x83004b4b, 0xc2c406a9, 0x8300cad5, 0x82c605b5, 0x82c402b6, 0xc300895e,
            0x82c6092f, 0x82c40497, 0x82fe4696, 0xc2c40d4a, 0x8300cea5, 0x82c60d69, 0x82c6056d, 0xc301a2b5, 0x82c4026e, 0x82c4052e,
            0x83006cad, 0xc2c40c95, 0x82c40d4a, 0x83002f4a, 0x82c60b59, 0xc300c56d, 0x82c6055b, 0x82c4025d, 0x8300793b, 0xc2c4092b,
            0x82c40a95, 0x83015b15, 0x82c406ca, 0xc2c60ad5, 0x830112b6, 0x82c604bb, 0x8300925f, 0xc2c40257, 0x82c4052b, 0x82fe6aaa,
            0x82c60e95, 0xc2c406aa, 0x83003baa, 0x82c60ab5, 0x8300b4b7, 0xc2c404ae, 0x82c60a57, 0x82fe752d, 0x82c40d26, 0xc2c60d95,
            0x830055d5, 0x82c4056a, 0x82c6096d, 0xc300255d, 0x82c404ae, 0x8300aa4f, 0x82c40a4d, 0xc2c40d25, 0x83006d69, 0x82c60b55,
            0x82c4035a, 0xc3002aba, 0x82c6095b, 0x8301c49b, 0x82c40497, 0xc2c40a4b, 0x83008b2b, 0x82c406a5, 0x82c406d4, 0xc3034ab5,
            0x82c402b6, 0x82c60937, 0x8300252f, 0xc2c40497, 0x82fe964e, 0x82c40d4a, 0x82c60ea5, 0xc30166a9, 0x82c6056d, 0x82c402b6,
            0x8301385e, 0xc2c4092e, 0x8300bc97, 0x82c40a95, 0x82c40d4a, 0xc3008daa, 0x82c60b4d, 0x82c6056b, 0x830042db, 0xc2c4025d,
            0x82c4092d, 0x83002d33, 0x82c40a95, 0xc3009b4d, 0x82c406aa, 0x82c60ad5, 0x83006575, 0xc2c604bb, 0x82c4025b, 0x83013457,
            0x82c4052b, 0xc2ffba94, 0x82c60e95, 0x82c406aa, 0x83008ada, 0xc2c609b5, 0x82c404b6, 0x83004aae, 0x82c60a4f, 0xc2c20526,
            0x83012d26, 0x82c60d55, 0x8301a5a9, 0xc2c4056a, 0x82c6096d, 0x8301649d, 0x82c4049e, 0xc2c40a4d, 0x83004d4d, 0x82c40d25,
            0x8300bd53, 0xc2c40b54, 0x82c60b5a, 0x8301895a, 0x82c6095b, 0xc2c4049b, 0x83004a97, 0x82c40a4b, 0x82c40aa5, 0xc3001ea5,
            0x82c406d4, 0x8302badb, 0x82c402b6, 0xc2c60937, 0x830064af, 0x82c40497, 0x82c4064b, 0xc2fe374a, 0x82c60da5, 0x8300b6b5,
            0x82c6056d, 0xc2c402ba, 0x8300793e, 0x82c4092e, 0x82c40c96, 0xc3015d15, 0x82c40d4a, 0x82c60da5, 0x83013555, 0xc2c4056a,
            0x83007a7a, 0x82c60a5d, 0x82c4092d, 0xc3006aab, 0x82c40a95, 0x82c40b4a, 0x83004baa, 0xc2c60ad5, 0x82c4055a, 0x830128ba,
            0x82c60a5b, 0xc3007537, 0x82c4052b, 0x82c40693, 0x83015715, 0xc2c406aa, 0x82c60ad9, 0x830035b5, 0x82c404b6, 0xc3008a5e,
            0x82c40a4e, 0x82c40d26, 0x83006ea6, 0xc2c40d52, 0x82c60daa, 0x8301466a, 0x82c6056d, 0xc2c404ae, 0x83003a9d, 0x82c40a4d,
            0x83007d2b, 0xc2c40b25, 0x82c40d52, 0x83015d54, 0x82c60b5a, 0xc2c6055d, 0x8300355b, 0x82c4049d, 0x83007657, 0x82c40a4b,
            0x82c40aa5, 0x83006b65, 0x82c406d2, 0xc2c60ada, 0x830045b6, 0x82c60937, 0x82c40497, 0xc3003697, 0x82c40a4d, 0x82fe76aa,
            0x82c60da5, 0xc2c405aa, 0x83005aec, 0x82c60aae, 0x82c4092e, 0xc3003d2e, 0x82c40c96, 0x83018d45, 0x82c40d4a, 0xc2c60d55,
            0x83016595, 0x82c4056a, 0x82c60a6d, 0xc300455d, 0x82c4052d, 0x82c40a95, 0x83003e95, 0xc2c40b4a, 0x83017b4a, 0x82c609d5,
            0x82c4055a, 0xc3015a3a, 0x82c60a5b, 0x82c4052b, 0x83014a17, 0xc2c40693, 0x830096ab, 0x82c406aa, 0x82c60ab5, 0xc30064f5,
            0x82c404b6, 0x82c60a57, 0x82fe452e, 0xc2c40d16, 0x82c60e93, 0x82fe3752, 0x82c60daa, 0xc30175aa, 0x82c6056d, 0x82c404ae,
            0x83015a1b, 0xc2c40a2d, 0x82c40d15, 0x83004da5, 0x82c40b52, 0xc3009d6a, 0x82c60ada, 0x82c6055d, 0x8301629b, 0xc2c4045b,
            0x82c40a2b, 0x83005b2b, 0x82c40a95, 0xc2c40b52, 0x83012ab2, 0x82c60ad6, 0x83017556, 0xc2c60537, 0x82c40457, 0x83005657,
            0x82c4052b, 0xc2c40695, 0x83003795, 0x82c405aa, 0x8300aab6, 0xc2c60a6d, 0x82c404ae, 0x8300696e, 0x82c40a56, 0xc2c40d2a,
            0x83005eaa, 0x82c60d55, 0x82c405aa, 0xc3003b6a, 0x82c60a6d, 0x830074bd, 0x82c404ab, 0xc2c40a8d, 0x83005d55, 0x82c40b2a,
            0x82c60b55, 0xc30045d5, 0x82c404da, 0x82c6095d, 0x83002557, 0xc2c4049b, 0x83006a97, 0x82c4064b, 0x82c406a9, 0x83004baa,
            0x82c606b5, 0x82c402ba, 0x83002ab6, 0xc2c60937, 0x82fe652e, 0x82c40d16, 0x82c60e4b, 0xc2fe56d2, 0x82c60da9, 0x82c605b5,
            0x8300336d, 0xc2c402ae, 0x82c40a2e, 0x83002e2d, 0x82c40c95, 0xc3006d55, 0x82c40b52, 0x82c60b69, 0x830045da, 0xc2c6055d,
            0x82c4025d, 0x83003a5b, 0x82c40a2b, 0xc3017a8b, 0x82c40a95, 0x82c40b4a, 0x83015b2a, 0xc2c60ad5, 0x82c6055b, 0x830042b7,
            0x82c40257, 0xc300952f, 0x82c4052b, 0x82c40695, 0x830066d5, 0xc2c405aa, 0x82c60ab5, 0x8300456d, 0x82c404ae, 0xc2c60a57,
            0x82ff3456, 0x82c40d2a, 0x83017e8a, 0xc2c60d55, 0x82c405aa, 0x83005ada, 0x82c6095d, 0xc2c404ae, 0x83004aab, 0x82c40a4d,
            0x83008d2b, 0xc2c40b29, 0x82c60b55, 0x83007575, 0x82c402da, 0xc2c6095d, 0x830054d7, 0x82c4049b, 0x82c40a4b, 0xc3013a4b,
            0x82c406a9, 0x83008ad9, 0x82c606b5, 0xc2c402b6, 0x83015936, 0x82c60937, 0x82c40497, 0xc2fe4696, 0x82c40e4a, 0x8300aea6,
            0x82c60da9, 0xc2c605ad, 0x830162ad, 0x82c402ae, 0x82c4092e, 0xc3005cad, 0x82c40c95, 0x82c40d4a, 0x83013d4a, 0xc2c60b69,
            0x8300757a, 0x82c6055b, 0x82c4025d, 0xc300595b, 0x82c4092b, 0x82c40a95, 0x83004d95, 0xc2c40b4a, 0x82c60b55, 0x830026d5,
            0x82c6055b, 0xc3006277, 0x82c40257, 0x82c4052b, 0x82fe5aaa, 0xc2c60e95, 0x82c406aa, 0x83003baa, 0x82c60ab5, 0x830084bd,
            0x82c404ae, 0x82c60a57, 0x82fe554d, 0xc2c40d26, 0x82c60d95, 0x83014655, 0x82c4056a, 0xc2c609ad, 0x8300255d, 0x82c404ae,
            0x83006a5b, 0xc2c40a4d, 0x82c40d25, 0x83005da9, 0x82c60b55, 0xc2c4056a, 0x83002ada, 0x82c6095d, 0x830074bb, 0xc2c4049b,
            0x82c40a4b, 0x83005b4b, 0x82c406a9, 0xc2c40ad4, 0x83024bb5, 0x82c402b6, 0x82c6095b, 0xc3002537, 0x82c40497, 0x82fe6656,
            0x82c40e4a, 0xc2c60ea5, 0x830156a9, 0x82c605b5, 0x82c402b6, 0xc30138ae, 0x82c4092e, 0x83017c8d, 0x82c40c95, 0xc2c40d4a,
            0x83016d8a, 0x82c60b69, 0x82c6056d, 0xc301425b, 0x82c4025d, 0x82c4092d, 0x83002d2b, 0xc2c40a95, 0x83007d55, 0x82c40b4a,
            0x82c60b55, 0xc3015555, 0x82c604db, 0x82c4025b, 0x83013857, 0xc2c4052b, 0x83008a9b, 0x82c40695, 0x82c406aa, 0xc3006aea,
            0x82c60ab5, 0x82c404b6, 0x83004aae, 0xc2c60a57, 0x82c40527, 0x82fe3726, 0x82c60d95, 0xc30076b5, 0x82c4056a, 0x82c609ad,
            0x830054dd, 0xc2c404ae, 0x82c40a4e, 0x83004d4d, 0x82c40d25, 0xc3008d59, 0x82c40b54, 0x82c60d6a, 0x8301695a, 0xc2c6095b,
            0x82c4049b, 0x83004a9b, 0x82c40a4b, 0xc300ab27, 0x82c406a5, 0x82c406d4, 0x83026b75, 0xc2c402b6, 0x82c6095b, 0x830054b7,
            0x82c40497, 0xc2c4064b, 0x82fe374a, 0x82c60ea5, 0x830086d9, 0xc2c605ad, 0x82c402b6, 0x8300596e, 0x82c4092e, 0xc2c40c96,
            0x83004e95, 0x82c40d4a, 0x82c60da5, 0xc3002755, 0x82c4056c, 0x83027abb, 0x82c4025d, 0xc2c4092d, 0x83005cab, 0x82c40a95,
            0x82c40b4a, 0xc3013b4a, 0x82c60b55, 0x8300955d, 0x82c404ba, 0xc2c60a5b, 0x83005557, 0x82c4052b, 0x82c40a95, 0xc3004b95,
            0x82c406aa, 0x82c60ad5, 0x830026b5, 0xc2c404b6, 0x83006a6e, 0x82c60a57, 0x82c40527, 0xc2fe56a6, 0x82c60d93, 0x82c405aa,
            0x83003b6a, 0xc2c6096d, 0x8300b4af, 0x82c404ae, 0x82c40a4d, 0xc3016d0d, 0x82c40d25, 0x82c40d52, 0x83005dd4, 0xc2c60b6a,
            0x82c6096d, 0x8300255b, 0x82c4049b, 0xc3007a57, 0x82c40a4b, 0x82c40b25, 0x83015b25, 0xc2c406d4, 0x82c60ada, 0x830138b6]

    def __init__(self):
        self.lunarYear = 0
        self.lunarMonth = 0
        self.lunarDay = 0
        self.isIntercalation = False

        self.solarYear = 0
        self.solarMonth = 0
        self.solarDay = 0

        self.__gapjaYearInx = [0, 0, 0]
        self.__gapjaMonthInx = [0, 0, 1]
        self.__gapjaDayInx = [0, 0, 2]


    def LunarIsoFormat(self):
        dateStr = "%04d-%02d-%02d" % (self.lunarYear, self.lunarMonth, self.lunarDay)
        if self.isIntercalation :
            dateStr += " Intercalation"
        return dateStr

    def SolarIsoFormat(self):
        return "%04d-%02d-%02d" % (self.solarYear, self.solarMonth, self.solarDay)

    def __getLunarData(self, year):
        return self.KOREAN_LUNAR_DATA[year - self.KOREAN_LUNAR_BASE_YEAR]

    def __getLunarIntercalationMonth(self, lunarData):
        return (lunarData >> 12) & 0x000F

    def __getLunarDays(self, year, month=None, isIntercalation=None):
        lunarData = self.__getLunarData(year)

        if month is not None and isIntercalation is not None :
            if (isIntercalation == True) and (self.__getLunarIntercalationMonth(lunarData) == month):
                days = self.LUNAR_BIG_MONTH_DAY if ((lunarData >>16) & 0x01) > 0 else self.LUNAR_SMALL_MONTH_DAY
            else:
                days = self.LUNAR_BIG_MONTH_DAY if ((lunarData >> (12 - month)) & 0x01) > 0 else self.LUNAR_SMALL_MONTH_DAY
        else:
            days = (lunarData >> 17) & 0x01FF
        return days

    def __getLunarDaysBeforeBaseYear(self, year):
        days = 0
        for baseYear in range(self.KOREAN_LUNAR_BASE_YEAR, year+1):
            days += self.__getLunarDays(baseYear)
        return days

    def __getLunarDaysBeforeBaseMonth(self, year, month, isIntercalation):
        days = 0
        if (year >= self.KOREAN_LUNAR_BASE_YEAR) and (month > 0):
            for baseMonth in range(1, month+1):
                days += self.__getLunarDays(year, baseMonth, False)

            if isIntercalation == True:
                intercalationMonth = self.__getLunarIntercalationMonth(self.__getLunarData(year))
                if (intercalationMonth > 0) and intercalationMonth < month+1:
                    days += self.__getLunarDays(year, intercalationMonth, True)
        return days

    def __getLunarAbsDays(self, year, month, day, isIntercalation):
        days = self.__getLunarDaysBeforeBaseYear(year-1) + self.__getLunarDaysBeforeBaseMonth(year, month-1, True) + day
        if (isIntercalation == True) and (self.__getLunarIntercalationMonth(self.__getLunarData(year)) == month):
            days += self.__getLunarDays(year, month, False)
        return days

    def __isSolarIntercalationYear(self, lunarData):
        return ((lunarData >> 30) & 0x01) > 0

    def __getSolarDays(self, year, month=None):
        lunarData = self.__getLunarData(year)
        if month is not None :
            days = self.SOLAR_DAYS[12] if (month == 2) and self.__isSolarIntercalationYear(lunarData) else self.SOLAR_DAYS[month - 1]
            if (year == 1582) and (month == 10):
                days -= 10
        else:
            days = self.SOLAR_BIG_YEAR_DAY if self.__isSolarIntercalationYear(lunarData) else self.SOLAR_SMALL_YEAR_DAY
            if year == 1582 :
                days -= 10
        return days

    def __getSolarDaysBeforeBaseYear(self, year):
        days = 0
        for baseYear in range(self.KOREAN_LUNAR_BASE_YEAR, year+1):
            days += self.__getSolarDays(baseYear)
        return days

    def __getSolarDaysBeforeBaseMonth(self, year, month):
        days = 0
        for baseMonth in range(1, month+1):
            days += self.__getSolarDays(year, baseMonth)
        return days

    def __getSolarAbsDays(self, year, month, day):
        days = self.__getSolarDaysBeforeBaseYear(year-1) + self.__getSolarDaysBeforeBaseMonth(year, month-1) + day
        days -= self.SOLAR_LUNAR_DAY_DIFF
        return days

    def __setSolarDateByLunarDate(self, lunarYear, lunarMonth, lunarDay, isIntercalation):
        absDays = self.__getLunarAbsDays(lunarYear, lunarMonth, lunarDay, isIntercalation)
        solarYear = 0
        solarMonth = 0
        solarDay = 0

        solarYear = lunarYear if (absDays < self.__getSolarAbsDays(lunarYear+1, 1, 1)) else lunarYear+1

        for month in range(12, 0, -1) :
            absDaysByMonth = self.__getSolarAbsDays(solarYear, month, 1)
            if (absDays >= absDaysByMonth) :
                solarMonth = month
                solarDay = absDays - absDaysByMonth +1
                break

        if (solarYear == 1582) and (solarMonth == 10) and (solarDay > 4) :
            solarDay += 10

        self.solarYear = solarYear
        self.solarMonth = solarMonth
        self.solarDay  = solarDay

    def __setLunarDateBySolarDate(self, solarYear, solarMonth, solarDay):
        absDays = self.__getSolarAbsDays(solarYear, solarMonth, solarDay)
        lunarYear = solarYear if (absDays >= self.__getLunarAbsDays(solarYear, 1, 1, False)) else solarYear-1
        lunarMonth = 0
        lunarDay = 0
        isIntercalation = False

        for month in range(12, 0, -1) :
            absDaysByMonth = self.__getLunarAbsDays(lunarYear, month, 1, False)
            if absDays >= absDaysByMonth:
                lunarMonth = month
                if self.__getLunarIntercalationMonth(self.__getLunarData(lunarYear)) == month :
                    isIntercalation = absDays >= self.__getLunarAbsDays(lunarYear, month, 1, True)

                lunarDay = absDays - self.__getLunarAbsDays(lunarYear, lunarMonth, 1, isIntercalation) + 1
                break

        self.lunarYear = lunarYear
        self.lunarMonth = lunarMonth
        self.lunarDay = lunarDay
        self.isIntercalation = isIntercalation

    def __checkValidDate(self, isLunar, isIntercalation, year, month, day):
        isValid = False
        dateValue = year*10000 + month*100 + day
        #1582. 10. 5 ~ 1582. 10. 14 is not valid
        minValue = self.KOREAN_LUNAR_MIN_VALUE if isLunar else self.KOREAN_SOLAR_MIN_VALUE
        maxValue = self.KOREAN_LUNAR_MAX_VALUE if isLunar else self.KOREAN_SOLAR_MAX_VALUE

        if minValue <= dateValue and maxValue >= dateValue :
            if month > 0 and month < 13 and day > 0 :
                dayLimit = self.__getLunarDays(year, month, isIntercalation) if isLunar else self.__getSolarDays(year, month)
                if isLunar == False and year == 1582 and month == 10 :
                    if day > 4 and day < 15 :
                        return isValid
                    else:
                        dayLimit += 10

                if day <= dayLimit :
                    isValid = True

        return isValid

    def setLunarDate(self, lunarYear, lunarMonth, lunarDay, isIntercalation) :
        isValid = False
        if self.__checkValidDate(True, isIntercalation, lunarYear, lunarMonth, lunarDay):
            self.lunarYear = lunarYear
            self.lunarMonth = lunarMonth
            self.lunarDay = lunarDay
            self.isIntercalation = isIntercalation and (self.__getLunarIntercalationMonth(self.__getLunarData(lunarYear)) == lunarMonth)
            self.__setSolarDateByLunarDate(lunarYear, lunarMonth, lunarDay, isIntercalation)
            isValid = True
        return isValid

    def setSolarDate(self, solarYear, solarMonth, solarDay):
        isValid = False
        if self.__checkValidDate(False, False, solarYear, solarMonth, solarDay) :
            self.solarYear = solarYear
            self.solarMonth = solarMonth
            self.solarDay = solarDay
            self.__setLunarDateBySolarDate(solarYear, solarMonth, solarDay)
            isValid = True
        return isValid

    def __getGapJa(self):
        absDays = self.__getLunarAbsDays(self.lunarYear, self.lunarMonth, self.lunarDay, self.isIntercalation)
        if absDays > 0 :
            self.__gapjaYearInx[0] = ((self.lunarYear+7) - self.KOREAN_LUNAR_BASE_YEAR) % len(self.KOREAN_CHEONGAN)
            self.__gapjaYearInx[1] = (((self.lunarYear+7) - self.KOREAN_LUNAR_BASE_YEAR) % len(self.KOREAN_GANJI))

            monthCount = self.lunarMonth
            monthCount += 12 * (self.lunarYear - self.KOREAN_LUNAR_BASE_YEAR)
            self.__gapjaMonthInx[0] = (monthCount+5) % len(self.KOREAN_CHEONGAN)
            self.__gapjaMonthInx[1] = (monthCount+1) % len(self.KOREAN_GANJI)

            self.__gapjaDayInx[0] = (absDays+4) % len(self.KOREAN_CHEONGAN)
            self.__gapjaDayInx[1] = absDays % len(self.KOREAN_GANJI)

    def getGapJaString(self) :
        self.__getGapJa()
        gapjaStr = "%c%c%c %c%c%c %c%c%c" % (chr(self.KOREAN_CHEONGAN[self.__gapjaYearInx[0]]), chr(self.KOREAN_GANJI[self.__gapjaYearInx[1]]), chr(self.KOREAN_GAPJA_UNIT[self.__gapjaYearInx[2]]),
        chr(self.KOREAN_CHEONGAN[self.__gapjaMonthInx[0]]), chr(self.KOREAN_GANJI[self.__gapjaMonthInx[1]]), chr(self.KOREAN_GAPJA_UNIT[self.__gapjaMonthInx[2]]),
        chr(self.KOREAN_CHEONGAN[self.__gapjaDayInx[0]]), chr(self.KOREAN_GANJI[self.__gapjaDayInx[1]]), chr(self.KOREAN_GAPJA_UNIT[self.__gapjaDayInx[2]]))

        if self.isIntercalation == True :
            gapjaStr += " (%c%c)" % (chr(self.INTERCALATION_STR[0]), chr(self.KOREAN_GAPJA_UNIT[1]))
        return gapjaStr


    def getChineseGapJaString(self) :
        self.__getGapJa()
        gapjaStr = "%c%c%c %c%c%c %c%c%c" % (chr(self.CHINESE_CHEONGAN[self.__gapjaYearInx[0]]), chr(self.CHINESE_GANJI[self.__gapjaYearInx[1]]), chr(self.CHINESE_GAPJA_UNIT[self.__gapjaYearInx[2]]),
        chr(self.CHINESE_CHEONGAN[self.__gapjaMonthInx[0]]), chr(self.CHINESE_GANJI[self.__gapjaMonthInx[1]]), chr(self.CHINESE_GAPJA_UNIT[self.__gapjaMonthInx[2]]),
        chr(self.CHINESE_CHEONGAN[self.__gapjaDayInx[0]]), chr(self.CHINESE_GANJI[self.__gapjaDayInx[1]]), chr(self.CHINESE_GAPJA_UNIT[self.__gapjaDayInx[2]]))

        if self.isIntercalation == True :
            gapjaStr += " (%c%c)" % (chr(self.INTERCALATION_STR[1]), chr(self.CHINESE_GAPJA_UNIT[1]))
        return gapjaStr
