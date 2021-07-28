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

zone = []
time_buy = []
hash_buy = []
fee_buy = []
amout_buy = []
coin_buy = []
status_buy = []
queue_buy = []
time_sale = []
hash_sale = []
fee_sale = []
amout_sale = []
coin_sale = []
status_sale = []
queue_sale = []
data_frame = {}

# Config
clear_data = 0
cryptocurrency = 'IOST'
currency = 'THB_IOST'
high = 0.9
low = 0.5
grid = 0.01
amount = 500
fee = 0.25

# Bitkub API info
API_HOST = 'https://api.bitkub.com'
API_KEY = '417c20d3eb95b23ef69774e95156c57a'
API_SECRET = b'25a0a7883d478b8fe4e642013e7f463a'
bitkub_header = {
	'Accept': 'application/json',
	'Content-Type': 'application/json',
	'X-BTK-APIKEY': API_KEY
}

# Line API info
LINE_HOST = 'https://notify-api.line.me/api/notify'
LINE_TOKEN = 'VkxNJg1TutzwSZGDV8hQUZ31xjwxEVrEr3veEScdOvN'
line_header = {
	'content-type':'application/x-www-form-urlencoded',
    'Authorization':'Bearer ' + LINE_TOKEN
}

def line_message(message):
    data = {
	    'message': message
    }
    response = requests.post(LINE_HOST, headers=line_header, data=data)
    print('Line message:', response.json())

def sale_message(time, rate, receive, fee, profit, total_profit):
    message = 'Order filled\nTime: ' + time + '\nCoin: ' + currency + '\nRate: ' + rate + '\nReceive: ' + receive + ' THB\nFee: ' + fee + ' THB\n' + 'Profit: ' + profit + ' THB\n' + 'Total profit: ' + total_profit + ' THB'
    response = requests.post(LINE_HOST, headers=line_header, data={'message': message})
    print('Sale message:', response.json())

def error_message(cause):
    _last_time = datetime.now(tz = tz.gettz("Asia/Bangkok")).strftime("%Y-%m-%d %H:%M:%S")
    message = 'Bot error\nTime: ' + _last_time + '\nCause: ' + cause
    response = requests.post(LINE_HOST, headers=line_header, data={'message': message})
    print('Error message:', response.json())

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
        'Queue Buy': queue_buy,
        'Time Sale': time_sale,
        'Hash Sale': hash_sale,
        'Fee Sale': fee_sale,
        'Amout Sale': amout_sale,
        'Receive Sale': coin_sale,
        'Status Sale': status_sale,
        'Queue sale': queue_sale,
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

def wallet_check():
    data = {
	    'ts': get_time()
    }
    signature = sign(data)
    data['sig'] = signature
    response = requests.post(API_HOST + '/api/market/wallet', headers=bitkub_header, data=json_encode(data))
    if response.json()['error'] == 0:
        return response.json()['result']['THB']
    else:
        return 0

def amout_crypto_check():
    data = {
	    'ts': get_time()
    }
    signature = sign(data)
    data['sig'] = signature
    response = requests.post(API_HOST + '/api/market/wallet', headers=bitkub_header, data=json_encode(data))
    if response.json()['error'] == 0:
        return float(response.json()['result'][cryptocurrency])
    else:
        return 0

def hash_check(hash):
    global queue_data
    if hash != '':
        data = {
            'hash': hash,
            'ts': get_time()
        }
        signature = sign(data)
        data['sig'] = signature
        response = requests.post(API_HOST + '/api/market/order-info', headers=bitkub_header, data=json_encode(data))
        if response.json()['error'] == 0:
            queue_data = response.json()['result']
            return response.json()['result']['status']
        else:
            return response.json()['error']

def ticker(cur):
    response = requests.get('https://api.bitkub.com/api/market/ticker?sym=' + cur)
    ticker_data = response.json()[cur]
    return ticker_data

def books(cur):
    response = requests.get('https://api.bitkub.com/api/market/books?sym=' + cur + '&lmt=1000000')
    if (response.json()['error'] == 0):
        return response.json()['result']
    else:
        return 'error'

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
    response = requests.post(API_HOST + '/api/market/place-bid', headers=bitkub_header, data=json_encode(data))
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
    response = requests.post(API_HOST + '/api/market/place-ask', headers=bitkub_header, data=json_encode(data))
    return response

def start_bot():
    global zone, time_buy, hash_buy, fee_buy, amout_buy, coin_buy, status_buy, queue_buy, time_sale, hash_sale, fee_sale, amout_sale, coin_sale, status_sale, queue_sale
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
                queue_buy.append('')
                time_sale.append('')
                hash_sale.append('')
                fee_sale.append('')
                amout_sale.append('')
                coin_sale.append('')
                status_sale.append('')
                queue_sale.append('')

            for x in numpy.arange(high, low - grid, -grid):
                _rate = round(x, 4)
                _response = place_bid(currency, amount, _rate)
                _last_time = datetime.now(tz = tz.gettz("Asia/Bangkok")).strftime("%Y-%m-%d %H:%M:%S")
                _hash = _response.json()['result']['hash']
                _fee = str(float(_response.json()['result']['fee']) - float(_response.json()['result']['cre']))
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
            queue_buy = sheet.col_values(8)[1:]
            time_sale = sheet.col_values(9)[1:]
            hash_sale = sheet.col_values(10)[1:]
            fee_sale = sheet.col_values(11)[1:]
            amout_sale = sheet.col_values(12)[1:]
            coin_sale = sheet.col_values(13)[1:]
            status_sale = sheet.col_values(14)[1:]
            queue_sale = sheet.col_values(15)[1:]
            sheet_dataframe = {
                'Zone': zone,
                'Time Buy': time_buy,
                'Hash Buy': hash_buy,
                'Fee Buy': fee_buy,
                'Amout Buy': amout_buy,
                'Receive Buy': coin_buy,
                'Status Buy': status_buy,
                'Queue Buy': queue_buy,
                'Time Sale': time_sale,
                'Hash Sale': hash_sale,
                'Fee Sale': fee_sale,
                'Amout Sale': amout_sale,
                'Receive Sale': coin_sale,
                'Status Sale': status_sale,
                'Queue Sale': queue_sale
            }
            sheet_to_dataframe(sheet_dataframe)
            print(data_frame)
    else:
        print('Loss! Please check the configuration.')
        sys.exit()

def update_bot():
    _wallet = wallet_check()
    _books = books(currency)
    _queue = 0
    _hash_buy = sheet.col_values(3)
    _hash_buy.pop(0)
    _hash_sale = sheet.col_values(10)
    _hash_sale.pop(0)
    _rate_buy = sheet.col_values(1)
    _rate_buy.pop(0)
    _coin_sale = sheet.col_values(13)
    _coin_sale.pop(0)
    for x in range(len(_hash_buy)):
        _hash_check = hash_check(_hash_buy[x])
        if _hash_check == 'filled' and status_sale[x] != 'unfilled' and amout_crypto_check() >= float(coin_buy[x]):
            _rate = float(_rate_buy[x]) + grid
            _response = place_ask(currency, coin_buy[x], _rate)
            if _response.json()['error'] == 17 or _response.json()['error'] == 18:
                _rate = float(_rate_buy[x])
                if int(_coin_sale[x]) < amount and _wallet >= amount:
                    _coin_sale[x] = amount
                _response = place_bid(currency, _coin_sale[x], _rate)
                if _response.json()['error'] == 17 or _response.json()['error'] == 18:
                    status_buy[x] = 'Error: ' + str(_response.json()['error'])
                    error_message('Insufficient balance')
                else:
                    _last_time = datetime.now(tz = tz.gettz("Asia/Bangkok")).strftime("%Y-%m-%d %H:%M:%S")
                    _hash = _response.json()['result']['hash']
                    _fee = str(float(_response.json()['result']['fee']) - float(_response.json()['result']['cre']))
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
                _fee = str(float(_response.json()['result']['fee']) - float(_response.json()['result']['cre']))
                _amount = _response.json()['result']['amt']
                _coin = _response.json()['result']['rec']
                status_buy[x] = 'filled'
                queue_buy[x] = '-'
                time_sale[x] = _last_time
                hash_sale[x] = _hash
                fee_sale[x] = _fee
                amout_sale[x] = _amount
                coin_sale[x] = _coin
                status_sale[x] = 'unfilled'
                queue_sale[x] = 'Calculating'
        elif _hash_check == 24:
            _rate = float(_rate_buy[x])
            if int(_coin_sale[x]) < amount and _wallet >= amount:
                _coin_sale[x] = amount
            _response = place_bid(currency, _coin_sale[x], _rate)
            _last_time = datetime.now(tz = tz.gettz("Asia/Bangkok")).strftime("%Y-%m-%d %H:%M:%S")
            _hash = _response.json()['result']['hash']
            _fee = str(float(_response.json()['result']['fee']) - float(_response.json()['result']['cre']))
            _amount = _response.json()['result']['amt']
            _coin = _response.json()['result']['rec']
            time_buy[x] = _last_time
            hash_buy[x] = _hash
            fee_buy[x] = _fee
            amout_buy[x] = _amount
            coin_buy[x] = _coin
            status_buy[x] = 'unfilled'
        else:
            if queue_data['status'] == 'unfilled':
                while 1:
                    if _books['bids'][_queue][3] == float(queue_data['rate']) and round(_books['bids'][_queue][4], 2) == round(float(queue_data['amount']) / float(queue_data['rate']), 2):
                        break
                    else:
                        _queue += 1
                queue_buy[x] = _queue
                print('Queue: ' + str(_queue))
                _queue = 0
    
    for x in range(len(_hash_sale)):
        _hash_check = hash_check(_hash_sale[x])
        if _hash_check == 'filled':
            _last_time = datetime.now(tz = tz.gettz("Asia/Bangkok")).strftime("%Y-%m-%d %H:%M:%S")
            _statement = [
                _last_time,
                currency,
                str(float(sheet.row_values(x + 2)[0]) + grid),
                sheet.row_values(x + 2)[9],
                sheet.row_values(x + 2)[10],
                sheet.row_values(x + 2)[11],
                sheet.row_values(x + 2)[12],
                float(sheet.row_values(x + 2)[12]) - float(sheet.row_values(x + 2)[4]) - float(sheet.row_values(x + 2)[3])
            ]
            statement.insert_row(_statement, 2)
            _total_profit = statement.col_values(8)
            _total_profit.pop(0)
            _total_profit = [i for i in _total_profit]
            for i in range(0, len(_total_profit)):
                _total_profit[i] = float(_total_profit[i])
            sale_message(_statement[0], _statement[2], _statement[6], _statement[4], str(round(_statement[7], 2)), str(round(sum(_total_profit), 2)))
            _rate = float(_rate_buy[x])
            if float(_coin_sale[x]) < amount and _wallet >= amount:
                _coin_sale[x] = amount
            _response = place_bid(currency, _coin_sale[x], _rate)
            if _response.json()['error'] == 17 or _response.json()['error'] == 18:
                status_sale[x] = 'Error: ' + str(_response.json()['error'])
            else:
                _hash = _response.json()['result']['hash']
                _fee = str(float(_response.json()['result']['fee']) - float(_response.json()['result']['cre']))
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
                queue_sale[x] = '-'
                queue_buy[x] = 'Calculating'
        elif _hash_check == 24:
            time_sale[x] = ''
            hash_sale[x] = ''
            fee_sale[x] = ''
            amout_sale[x] = ''
            coin_sale[x] = ''
            status_sale[x] = ''
            queue_sale[x] = '-'
        else:
            if queue_data['status'] == 'unfilled':
                while 1:
                    if _books['asks'][_queue][3] == float(queue_data['rate']) and _books['asks'][_queue][4] == float(queue_data['amount']):
                        break
                    else:
                        _queue += 1
                queue_sale[x] = _queue
                print('Queue: ' + str(_queue))
                _queue = 0
    update_dataframe()
    set_with_dataframe(sheet, data_frame)
    print(data_frame)

start_bot()
while 1:
    try:
        update_bot()
    except Exception:
        error_message('API error')
        pass