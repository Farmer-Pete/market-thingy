import datetime
import pandas
import dateutil.parser
from bs4 import BeautifulSoup
from edgar.requests_wrapper import GetRequest
from dataclasses import dataclass


@dataclass
class FinancialInfo:
    map: dict
    date: str
    months: int = 3


@dataclass
class Report:
    reports: list


@dataclass
class Value:
    labels: str
    values: float


class Filing:
    def __init__(self, symbol: str, year: int, quarter: int):
        self.year = year
        self.quarter = quarter
        self.company = symbol
        self.base_url = base_url = f'https://www.marketwatch.com/investing/stock/{self.company.lower()}/financials'
        self.date_filed = datetime.datetime.today()

    def _download(self, page: str) -> str:
        url = f'{self.base_url}/{page}/quarter'
        print(f'Downloading: {url}...')
        return GetRequest(url).response.text

    def _parse_record(self, key: str, value: str) -> list:

        if value == '-':
            return key, Value(key, 0)

        multiplier = 1

        if value[0] == '(' and value[-1] == ')':
            value = value[1:-1]
            multiplier = -1

        if value[-1] == 'K':
            value = float(value[:-1])
            multiplier *= 1_000
        elif value[-1] == 'M':
            value = float(value[:-1])
            multiplier *= 1_000_000
        elif value[-1] == 'B':
            value = float(value[:-1])
            multiplier *= 1_000_000_000
        elif value[-1] == 'T':
            value = float(value[:-1])
            multiplier *= 1_000_000_000_000

        try:
            value = float(value)
        except ValueError:
            pass

        return key, Value([key], [value * multiplier])

    def _response_to_dict(self, response: str):
        soup = BeautifulSoup(response, features='lxml')
        tables = soup.select('.region--primary table.table')  # .select('tr td div.fixed--cell').decompose()

        # Clean out duplicate tags
        for table in tables:
            for cell in table.select('tr td div.fixed--cell'):
                cell.decompose()

        df = pandas.DataFrame()

        for table in pandas.read_html(str(tables)):
            df = df.append(table)

        datemap = dict()

        for column in df.columns:
            try:
                dateobj = pandas.to_datetime(column)
            except dateutil.parser.ParserError:
                continue

            key = (abs(dateobj.year - self.year),
                   abs(dateobj.quarter - self.quarter))

            datemap[key] = column

        return dict(
            self._parse_record(row[0], row[1])
            for idx, row in df[['Item Item', datemap[min(datemap.keys())]]].iterrows()
        )

    def get_balance_sheets(self):
        return Report([FinancialInfo(
            map=self._response_to_dict(self._download('balance-sheet')),
            date=f'{self.year}Q{self.quarter}'
        )])

    def get_cash_flows(self):
        return Report([FinancialInfo(
            map=self._response_to_dict(self._download('cash-flow')),
            date=f'{self.year}Q{self.quarter}'
        )])

    def get_income_statements(self):
        return Report([FinancialInfo(
            map=self._response_to_dict(self._download('income')),
            date=f'{self.year}Q{self.quarter}'
        )])


class Stock:

    def __init__(self, symbol: str):
        self.symbol = symbol

    def get_filing(self, period: str, year: int, quarter: int):
        if period != 'quarterly':
            raise NotImplementedError(f'Period not supported: {period}')

        return Filing(
            symbol=self.symbol,
            year=year,
            quarter=quarter
        )
