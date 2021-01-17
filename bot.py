from oauth2client.service_account import ServiceAccountCredentials
from gspread_dataframe import set_with_dataframe
from google.oauth2 import service_account
from google.auth.transport.requests import AuthorizedSession
from dateutil import tz
from datetime import datetime
import gspread
import hashlib
import hmac
import json
import requests
import time
import numpy
import sys
import pandas

credentials = service_account.Credentials.from_service_account_file(
    'credentials.json')
scoped_credentials = credentials.with_scopes(
        ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']
        )
gc = gspread.Client(auth = scoped_credentials)
gc.session = AuthorizedSession(scoped_credentials)
spreadsheet_key = '19KHfna-TDVBdwPowCtSt8oUe3VpzzSWRFmZVX0G2448'
sheet = gc.open_by_key(spreadsheet_key).sheet1
statement = gc.open_by_key(spreadsheet_key).worksheet('Statement')

# Config
clear_data = 0
cryptocurrency = 'THB_IOST'
high = 0.80
low = 0.40
grid = 0.01
amount = 10
fee = 0.25

zone = []
time_buy = []
hash_buy = []
fee_buy = []
amout_buy = []
coin_buy = []
status_buy = []
time_sale = []
hash_sale = []
fee_sale = []
amout_sale = []
coin_sale = []
status_sale = []

data_frame = {}

# API info
API_HOST = 'https://api.bitkub.com'
API_KEY = '417c20d3eb95b23ef69774e95156c57a'
API_SECRET = b'25a0a7883d478b8fe4e642013e7f463a'

header = {
	'Accept': 'application/json',
	'Content-Type': 'application/json',
	'X-BTK-APIKEY': API_KEY,
}

def percentage(percent, whole):
    return (percent * whole) / 100.0

def json_encode(data):
	return json.dumps(data, separators=(',', ':'), sort_keys=True)

def sign(data):
	j = json_encode(data)
	print('Signing payload: ' + j)
	h = hmac.new(API_SECRET, msg=j.encode(), digestmod=hashlib.sha256)
	return h.hexdigest()

def get_time():
    response = requests.get(API_HOST + '/api/servertime')
    ts = int(response.text)
    return ts

def sheet_to_dataframe(data):
    global data_frame
    data_frame = pandas.DataFrame(data)

def update_dataframe():
    global data_frame
    _data_frame = {
        'Zone': zone,
        'Time Buy': time_buy,
        'Hash Buy': hash_buy,
        'Fee Buy': fee_buy,
        'Amout Buy': amout_buy,
        'Receive Buy': coin_buy,
        'Status Buy': status_buy,
        'Time Sale': time_sale,
        'Hash Sale': hash_sale,
        'Fee Sale': fee_sale,
        'Amout Sale': amout_sale,
        'Receive Sale': coin_sale,
        'Status Sale': status_sale
    }
    data_frame = pandas.DataFrame(_data_frame)

def zone_position(zone_name):
    position = 0
    for x in zone:
        if x == zone_name:
            return position
        position += 1

def loss_check():
    rate_sale = high + grid
    sale = (amount - percentage(fee, amount)) / high
    profit = (sale * rate_sale) - percentage(fee, amount) - amount
    if profit < 0:
        return 'loss'
    else:
        return 'profit'

def hash_check(hash):
    if hash != '':
        data = {
            'hash': hash,
            'ts': get_time()
        }
        signature = sign(data)
        data['sig'] = signature
        response = requests.post(API_HOST + '/api/market/order-info', headers=header, data=json_encode(data))
        if response.json()['error'] == 24:
            return 'order_cancelled'
        else:
            return response.json()['result']['status']

def ticker(cur):
    response = requests.get('https://api.bitkub.com/api/market/ticker?sym=' + cur)
    ticker_data = response.json()[cur]
    return ticker_data

def calculate_chart(cur):
    response = requests.get('https://tradingview.bitkub.com/tradingview/history?symbol=' + cur + '&resolution=1&from=' + str(get_time() - 1000) + '&to=' + str(get_time()))
    chart_data = response.json()['c']
    return chart_data

def place_bid(cur, amt, rat):
    data = {
        'sym': cur,
        'amt': amt,
        'rat': rat,
        'typ': 'limit',
        'ts': get_time(),
    }
    signature = sign(data)
    data['sig'] = signature
    response = requests.post(API_HOST + '/api/market/place-bid', headers=header, data=json_encode(data))
    return response

def place_ask(cur, amt, rat):
    data = {
        'sym': cur,
        'amt': amt,
        'rat': rat,
        'typ': 'limit',
        'ts': get_time(),
    }
    signature = sign(data)
    data['sig'] = signature
    response = requests.post(API_HOST + '/api/market/place-ask', headers=header, data=json_encode(data))
    return response

def start_bot():
    global zone, time_buy, hash_buy, fee_buy, amout_buy, coin_buy, status_buy, time_sale, hash_sale, fee_sale, amout_sale, coin_sale, status_sale
    if loss_check() == 'profit':
        if clear_data == 1:
            gc.open_by_key(spreadsheet_key).values_clear('Status')
            for x in numpy.arange(low - grid, high, grid) + grid:
                zone.append(round(x, 4))
                time_buy.append('')
                hash_buy.append('')
                fee_buy.append('')
                amout_buy.append('')
                coin_buy.append('')
                status_buy.append('')
                time_sale.append('')
                hash_sale.append('')
                fee_sale.append('')
                amout_sale.append('')
                coin_sale.append('')
                status_sale.append('')

            for x in numpy.arange(high, low - grid, -grid):
                _rate = round(x, 4)
                _response = place_bid(cryptocurrency, amount, _rate)
                _last_time = datetime.now(tz = tz.gettz("Asia/Bangkok")).strftime("%Y-%m-%d %H:%M:%S")
                _hash = _response.json()['result']['hash']
                _fee = _response.json()['result']['fee']
                _amount = _response.json()['result']['amt']
                _coin = _response.json()['result']['rec']

                time_buy[zone_position(_rate)] = _last_time
                hash_buy[zone_position(_rate)] = _hash
                fee_buy[zone_position(_rate)] = _fee
                amout_buy[zone_position(_rate)] = _amount
                coin_buy[zone_position(_rate)] = _coin
                status_buy[zone_position(_rate)] = 'unfilled'
            update_dataframe()
            set_with_dataframe(sheet, data_frame)
            print(data_frame)
        else:
            zone = sheet.col_values(1)[1:]
            time_buy = sheet.col_values(2)[1:]
            hash_buy = sheet.col_values(3)[1:]
            fee_buy = sheet.col_values(4)[1:]
            amout_buy = sheet.col_values(5)[1:]
            coin_buy = sheet.col_values(6)[1:]
            status_buy = sheet.col_values(7)[1:]
            time_sale = sheet.col_values(8)[1:]
            hash_sale = sheet.col_values(9)[1:]
            fee_sale = sheet.col_values(10)[1:]
            amout_sale = sheet.col_values(11)[1:]
            coin_sale = sheet.col_values(12)[1:]
            status_sale = sheet.col_values(13)[1:]
            sheet_dataframe = {
                'Zone': zone,
                'Time Buy': time_buy,
                'Hash Buy': hash_buy,
                'Fee Buy': fee_buy,
                'Amout Buy': amout_buy,
                'Receive Buy': coin_buy,
                'Status Buy': status_buy,
                'Time Sale': time_sale,
                'Hash Sale': hash_sale,
                'Fee Sale': fee_sale,
                'Amout Sale': amout_sale,
                'Receive Sale': coin_sale,
                'Status Sale': status_sale
            }
            sheet_to_dataframe(sheet_dataframe)
            print(data_frame)
    else:
        print('Loss! Please check the configuration.')
        sys.exit()

def update_bot():
    _hash_buy = sheet.col_values(3)
    _hash_buy.pop(0)
    _hash_sale = sheet.col_values(9)
    _hash_sale.pop(0)
    _rate_buy = sheet.col_values(1)
    _rate_buy.pop(0)
    _coin_buy = sheet.col_values(6)
    _coin_buy.pop(0)
    _coin_sale = sheet.col_values(12)
    _coin_sale.pop(0)
    for x in range(len(_hash_buy)):
        _hash_check = hash_check(_hash_buy[x])
        if _hash_check == 'filled' and status_sale[x] != 'unfilled':
            _rate = float(_rate_buy[x]) + grid
            _response = place_ask(cryptocurrency, _coin_buy[x], _rate)
            if _response.json()['error'] == 17 or _response.json()['error'] == 18:
                _rate = float(_rate_buy[x])
                _response = place_bid(cryptocurrency, amount, _rate)
                if _response.json()['error'] == 17 or _response.json()['error'] == 18:
                    status_buy[x] = _response.json()['error']
                else:    
                    _last_time = datetime.now(tz = tz.gettz("Asia/Bangkok")).strftime("%Y-%m-%d %H:%M:%S")
                    _hash = _response.json()['result']['hash']
                    _fee = _response.json()['result']['fee']
                    _amount = _response.json()['result']['amt']
                    _coin = _response.json()['result']['rec']
                    time_buy[x] = _last_time
                    hash_buy[x] = _hash
                    fee_buy[x] = _fee
                    amout_buy[x] = _amount
                    coin_buy[x] = _coin
                    status_buy[x] = 'unfilled'
            else:
                _last_time = datetime.now(tz = tz.gettz("Asia/Bangkok")).strftime("%Y-%m-%d %H:%M:%S")
                _hash = _response.json()['result']['hash']
                _fee = _response.json()['result']['fee']
                _amount = _response.json()['result']['amt']
                _coin = _response.json()['result']['rec']
                status_buy[x] = 'filled'
                time_sale[x] = _last_time
                hash_sale[x] = _hash
                fee_sale[x] = _fee
                amout_sale[x] = _amount
                coin_sale[x] = _coin
                status_sale[x] = 'unfilled'
        elif _hash_check == 'order_cancelled':
            _rate = float(_rate_buy[x])
            _response = place_bid(cryptocurrency, amount, _rate)
            _last_time = datetime.now(tz = tz.gettz("Asia/Bangkok")).strftime("%Y-%m-%d %H:%M:%S")
            _hash = _response.json()['result']['hash']
            _fee = _response.json()['result']['fee']
            _amount = _response.json()['result']['amt']
            _coin = _response.json()['result']['rec']
            time_buy[x] = _last_time
            hash_buy[x] = _hash
            fee_buy[x] = _fee
            amout_buy[x] = _amount
            coin_buy[x] = _coin
            status_buy[x] = 'unfilled'
    
    for x in range(len(_hash_sale)):
        _hash_check = hash_check(_hash_sale[x])
        if _hash_check == 'filled':
            _last_time = datetime.now(tz = tz.gettz("Asia/Bangkok")).strftime("%Y-%m-%d %H:%M:%S")
            _statement = [
                _last_time, 
                sheet.row_values(x + 2)[8],
                sheet.row_values(x + 2)[9],
                sheet.row_values(x + 2)[10],
                sheet.row_values(x + 2)[11],
                float(sheet.row_values(x + 2)[11]) - float(amout_buy[x])
            ]
            statement.insert_row(_statement, 2)
            _rate = float(_rate_buy[x])
            _response = place_bid(cryptocurrency, _coin_sale[x], _rate)
            _hash = _response.json()['result']['hash']
            _fee = _response.json()['result']['fee']
            _amount = _response.json()['result']['amt']
            _coin = _response.json()['result']['rec']
            time_buy[x] = _last_time
            hash_buy[x] = _hash
            fee_buy[x] = _fee
            amout_buy[x] = _amount
            coin_buy[x] = _coin
            status_buy[x] = 'unfilled'
            time_sale[x] = ''
            hash_sale[x] = ''
            fee_sale[x] = ''
            amout_sale[x] = ''
            coin_sale[x] = ''
            status_sale[x] = ''
        elif _hash_check == 'order_cancelled':
            time_sale[x] = ''
            hash_sale[x] = ''
            fee_sale[x] = ''
            amout_sale[x] = ''
            coin_sale[x] = ''
            status_sale[x] = ''
    update_dataframe()
    set_with_dataframe(sheet, data_frame)
    print(data_frame)

start_bot()

while 1:
    try:
        update_bot()
    except Exception:
        pass