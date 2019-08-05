# Anniversary Sensor for Home Assistant

홈어시스턴트 커스텀 컴포넌트입니다.\
기념일 D-Day를 센서로 알려줍니다.
- 음력을 지원합니다.
- 등록된 기념일의 양력, 음력을 변환하여 속성값으로 알려줍니다.
- 다가올 기념일 날짜도 알려줍니다.
- 기념일에서 현재 날짜까지의 일자 카운트도 알려줍니다.
- TTS 로 사용할 수 있는 문구를 별도 센서 `sensor.anniversary_tts` 로 자동 생성합니다.
- [Lovelace UI 커스텀 카드](https://github.com/GrecHouse/anniversary-lovelace-card)를 이용할 수 있습니다.

<br>
<img src="https://raw.githubusercontent.com/GrecHouse/anniversary/master/Screenshot_2019-07-01-15-03-13-797_com.android.chrome~01~02.png" width="500px" />
<br>
<img src="https://raw.githubusercontent.com/GrecHouse/anniversary/master/Screenshot_2019-07-01-15-04-00-992_com.android.chrome~01~01.png" width="400px" />
<br>

## Version history
| Version | Date        |               |
| :-----: | :---------: | ------------- |
| v1.0    | 2019.07.04  | First version  |
| v1.1    | 2019.07.05  | 음력여부(is_lunar) 속성 추가 |
| v1.2    | 2019.07.15  | 장보기목록(shopping list) - anniversary_tts 센서 연동 기능 추가 | 
| v1.21   | 2019.07.16  | 음력 comming date 버그 수정 |
| v1.22   | 2019.08.05  | 장보기목록 설정 오류시 회피 처리 |

<br>

## Installation

- HA 설치 경로 아래 custom_component 에 파일을 넣어줍니다.\
`<config directory>/custom_components/anniversary/__init__.py`\
`<config directory>/custom_components/anniversary/manifest.json`\
`<config directory>/custom_components/anniversary/sensor.py`
- configuration.yaml 파일에 설정을 추가합니다.
- Home-Assistant 를 재시작합니다.

<br>


## Usage

### configuration
- HA 설정에 anniversary sensor를 추가합니다.

```yaml
sensor:
  - platform: anniversary
    tts_days: 3
    sensors:
      birthday_hong:
        name: '홍길동 생일'
        date: '2019-03-03'
        type: 'birth'
      wedding:
        name: '결혼기념일'
        date: '2017-12-31'
        type: 'wedding'
      steve_jobs:
        name: '스티브잡스 기일'
        date: '2011-09-09'
        type: 'memorial'
        lunar: true
        intercalation: false
```

<br>

### 기본 설정값

|옵션|값|
|--|--|
|platform| (필수) anniversary |
|sensors| (필수) 센서로 등록할 기념일 정보를 추가 |
|tts_days| (옵션) TTS 문구로 자동 생성할 일수<br>지정한 일수 이하일때 문구로 추가됨<br>기본값은 3일 |
|tts_scan_interval | (옵션) 장보기목록 스캔 주기 (seconds)<br>미설정시 매일 자정에 1번만 갱신 |


### 센서별 설정값

|옵션|값|
|--|--|
|date| (필수) 기념일 날짜 |
|name| (옵션) 기념일 이름. 지정하지 않으면 센서명으로 저장됨 |
|type| (옵션) 기념일 종류. 기본값은 anniversary |
|lunar| (옵션) 음력여부. 기본값은 false |
|intercalation| (옵션) 음력-윤달여부. 기본값은 false |


### 기념일 종류 (type) 옵션

|종류|설명|
|--|--|
|anniversary|기본값|
|birth|생일|
|memorial|기일|
|wedding|결혼기념일|

- type 에 따라 아이콘이 다르게 보입니다.
- 4가지 타입 외에 임의의 타입을 선언해서 사용해도 무방합니다.\
단, 아이콘은 기본값과 동일하게 보입니다.


### 장보기목록(shopping list)을 이용한 TTS 센서 문구 추가 (v1.2 이후)
- HA 화면의 `장보기목록` 에 아래 샘플처럼 `양` 또는 `음`으로 시작되는 항목을 추가하면 TTS 문구로 생성됩니다.
- 또한 추가된 항목은 `sensor.anniversary_tts` 의 속성값으로 추가됩니다. 
- [Lovelace UI 커스텀 카드](https://github.com/GrecHouse/anniversary-lovelace-card) 에도 추가됩니다.
- 음력 윤달인 경우에는 타이틀에 `(윤)`을 추가하면 됩니다.

```text
[양/음][날짜-월일]-[타이틀]

양0715-정수기 필터 교체
음0511-음력일반샘플
음0511-음력윤달샘플(윤)
```

<br>

## korean-lunar-calendar 라이브러리 소스를 이용합니다.
- https://pypi.org/project/korean-lunar-calendar/
- https://github.com/usingsky/korean_lunar_calendar_py

<br>

## 버그 또는 문의사항
네이버 카페 [SmartThings&IoT Home](https://cafe.naver.com/stsmarthome/) `그레고리하우스`

