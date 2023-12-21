import os
import uuid
import matplotlib.pyplot as plt
from pathlib import Path
from typing import Any
from datetime import datetime
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import MinMaxScaler


class PredictionModel:
    scaler: MinMaxScaler
    func: Any
    model: LinearRegression
    path_to_figs_folder: Path
    name: str

    def __init__(self, prices, datetimes, init_dt, name):
        self.prices = np.array(prices).reshape(-1, 1)
        self.first_datetime = init_dt
        datetimes = np.array(datetimes)
        datetimes = np.array(
            [dt.total_seconds() // 3600 for dt in (datetimes - init_dt)]
        ).reshape(-1, 1)
        self.datetimes = np.array(datetimes).reshape(-1, 1)
        self.coefs = []
        if os.getenv('PATH_TO_FIGS_FOLDER') is None:
            self.path_to_figs_folder = Path("C:\\Users\\OMEN\\Desktop\\target_practice\\figs")
        else:
            self.path_to_figs_folder = Path(os.getenv('PATH_TO_FIGS_FOLDER'))
        self.name = name

    def transform_data(self):
        scaler = MinMaxScaler()
        scaler.fit(self.prices)
        self.prices = scaler.transform(self.prices)
        self.scaler = scaler

    def train(self):
        lr = LinearRegression()
        lr.fit(self.datetimes, self.prices)

        def func(x):
            y = x * lr.coef_ + lr.intercept_
            return y

        self.model = lr
        self.func = func
        self.coefs = [lr.coef_, lr.intercept_]

    def predict(self, dt: datetime):
        hours_passed = (dt - self.first_datetime).total_seconds() // 3600
        estimated_price = self.func(hours_passed)
        return np.round(self.scaler.inverse_transform(estimated_price), 2)

    @classmethod
    def get_func(cls, coef, intercept):
        def func(x):
            y = x * coef + intercept
            return y

        return func

    def draw_graph(self, date_range):
        fig, ax = plt.subplots()
        ax.plot(date_range, self.scaler.inverse_transform(self.prices), 'b')
        ax.plot(date_range, self.scaler.inverse_transform(self.func(self.datetimes)), color='orange')
        filename = uuid.uuid4().hex + '.png'
        fig.autofmt_xdate()
        fig.savefig(self.path_to_figs_folder.joinpath(filename))
        plt.close(fig)
        return self.path_to_figs_folder.joinpath(filename)
