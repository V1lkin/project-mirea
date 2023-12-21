import requests
import string
import json
from datetime import datetime, timezone


class SteamParser:
    steam_item_url = "https://steamcommunity.com/market/listings/730/{name}"
    search_history_start = "var line1="
    search_history_end = ";\r\n\t\t\tg_timePriceHistoryEarliest = new Date();"

    replace_dates = {
        "Dec": '12',
        "Jan": '1',
        "Feb": "2",
        "Mar": "3",
        "Apr": '4',
        "May": '5',
        "Jun": '6',
        "Jul": '7',
        "Aug": '8',
        "Sep": '9',
        "Oct": '10',
        "Nov": '11'
    }
    dt_format = "%m %d %Y %H: +0"

    @classmethod
    def get_item(cls, name, dt_from: datetime = None):
        resp = requests.get(cls.steam_item_url.format(name=name))
        price_history, datetime_labels = SteamParser.get_price_history(resp, dt_from)
        return price_history, datetime_labels

    @classmethod
    def get_price_history(cls, resp: requests.Response, dt_from: datetime = None):
        text = resp.text
        start_index = text.find(cls.search_history_start) + len(cls.search_history_start)
        end_index = text.find(cls.search_history_end)
        prices = []
        datetime_labels = []
        for price in json.loads(text[start_index:end_index]):
            dt = price[0]
            for k, v in cls.replace_dates.items():
                dt = dt.replace(k, v)
            dt = datetime.strptime(dt, cls.dt_format).replace(tzinfo=timezone.utc)
            if dt_from is not None and dt < dt_from:
                continue
            datetime_labels.append(dt)
            prices.append(float(price[1]))
        return prices, datetime_labels
