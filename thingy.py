import market_watch
import datetime
import edgar.stock
import yaml
import collections
from typing import Union, Optional
from dataclasses import dataclass
from edgar.financials import FinancialInfo
from wheezy.template.engine import Engine
from wheezy.template.ext.core import CoreExtension
from wheezy.template.loader import FileLoader


class FallThruDict(dict):
    def __init__(self, source: FinancialInfo):
        self._months = source.months
        self._factor = 1

        if self._months:
            self._factor = source.months / 3

        super().__init__(source.map)

    def __getitem__(self, keys: Union[list, str]) -> float:
        if isinstance(keys, str):
            keys = [keys]

        # Look up by key
        key_results = [sum(element.values) / self._factor
                       for key in keys
                       if (element := dict.get(self, key))]
        # Look up by label
        label_results = [sum(element.values) / self._factor
                         for element in self.values()
                         if (set(label.lower() for label in element.labels)
                             & set(label.lower() for label in keys))]

        results = key_results + label_results

        if not results:
            # Key not found
            raise KeyError(keys)

        for result in results:
            if result:
                # Non-zero value found
                return result

        # Welp, we got a zero value, but at least it is something
        return results[-1]

    def __contains__(self, keys: Union[list, str]) -> bool:
        if isinstance(keys, str):
            keys = [keys]

        mykeys = self.keys()

        for key in keys:
            if key in mykeys:
                return True
        return False

    def get(self, keys: Union[list, str]) -> Optional[float]:
        if keys in self:
            return self[keys]


class Stock:
    def __init__(self, symbol: str, period: str = 'annual', year: int = 0, quarter: int = 0):
        self.symbol = symbol

        if len(symbol) <= 4:
            self.stock = edgar.stock.Stock(self.symbol)
        else:
            self.stock = market_watch.Stock(self.symbol)
        self.filing = self.stock.get_filing(period, year, quarter)

        print(f'=== [{self.filing.company}] - {self.filing.date_filed.isoformat()} ===')

        self.facts = Facts.new(
            balance_sheet=FallThruDict(
                self.recent_quarterly_report(self.filing.get_balance_sheets().reports)),
            cash_flow=FallThruDict(
                self.recent_quarterly_report(self.filing.get_cash_flows().reports)),
            income_statements=FallThruDict(
                self.recent_quarterly_report(self.filing.get_income_statements().reports)),
        )

        self.liquidity_ratios = LiquidityRatios.new(self.facts)
        self.leverage_financial_ratios = LeverageFinancialRatios.new(self.facts)
        self.profitability_ratios = ProfitabilityRatios.new(self.facts)

    def recent_quarterly_report(self, reports: list) -> FinancialInfo:
        for months in (3, 6, 9, None):
            selected_reports = [(report.date, idx)
                                for idx, report in enumerate(reports)
                                if report.months == months]
            if selected_reports:
                date, idx = max(selected_reports)
                return reports[idx]
        breakpoint()
        raise ValueError('Not able to find any reports')

    def export(self, commas=True) -> dict:
        return dict(
            facts=self.facts.export(commas),
            liquidity_ratios=self.liquidity_ratios.export(commas),
            leverage_financial_ratios=self.leverage_financial_ratios.export(commas),
            profitability_ratios=self.profitability_ratios.export(commas),
        )

    @staticmethod
    def export_meta() -> dict:
        return dict(
            facts=Facts.export_meta(),
            liquidity_ratios=LiquidityRatios.export_meta(),
            leverage_financial_ratios=LeverageFinancialRatios.export_meta(),
            profitability_ratios=ProfitabilityRatios.export_meta(),
        )


class HistoricalStock:
    def __init__(self, symbol: str, period: str, years: list, quarters: list):
        self.reports = [
            Stock(symbol, period, year, quarter).export(commas=False)
            for year in years
            for quarter in quarters
        ]

    def export(self) -> dict:
        result = collections.defaultdict(lambda: collections.defaultdict(list))
        for report in self.reports:
            for source, data in report.items():
                for key, value in data.items():
                    result[source][key].append(value)

        return {
            source: {key: ','.join(values) for key, values in data.items()}
            for source, data in result.items()
        }


class _Exportable:
    def export(self, commas=True) -> dict:
        return {
            key.replace('_', ' ').title(): format(value, ',.2f' if commas else 'f')
            for key, value in self.__dict__.items()
        }

    @classmethod
    def export_meta(cls) -> Union[list, dict]:
        try:
            data = yaml.safe_load(cls.__doc__)
            if isinstance(data, dict):
                return {key.replace('_', ' ').title(): value for key, value in data.items()}
        except yaml.scanner.ScannerError:
            pass

        return [
            key.replace('_', ' ').title() for key in cls.__annotations__
        ]


@dataclass
class Facts(_Exportable):

    total_assets: float
    total_equity: float
    total_liabilities: float

    current_assets: float
    current_equity: float
    current_liabilities: float

    non_current_assets: float
    non_current_equity: float
    non_current_liabilities: float

    cash_and_cash_equivalents: float
    interest_expenses: float
    net_income: float
    operating_income: float
    shareholders_equity: float
    #preferred_equity: float
    #total_common_shares_outstanding: float

    @classmethod
    def new(cls,
            balance_sheet: FallThruDict,
            cash_flow: FallThruDict,
            income_statements: FallThruDict):

        current_assets = balance_sheet[
            'us-gaap_AssetsCurrent',
            'Total Current Assets'
        ]

        current_liabilities = balance_sheet[
            'us-gaap_LiabilitiesCurrent',
            'Total Current Liabilities'
        ]

        total_assets = balance_sheet[
            'us-gaap_Assets',
            'Total Assets'
        ]

        shareholders_equity = balance_sheet[
            'us-gaap_StockholdersEquity',
            'us-gaap_EquityMethodInvestments',
            'us-gaap_StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',
            'Total Shareholders\' Equity',
        ]

        cash_and_cash_equivalents = balance_sheet[
            'us-gaap_Cash',
            'Cash',
            'Cash and cash equivalents',
            'Cash & Short Term Investments',
        ]

        interest_expenses = income_statements[
            'us-gaap_InterestExpense',
            'us-gaap_InterestExpenseDebt',
            'Total Interest Expense',
            'Interest Expense',
            'Interest income',
            'Interest expense, net',
        ]

        if not (net_income := cash_flow.get(['us-gaap_NetIncomeLoss',
                                             'us-gaap_ProfitLoss'])):

            net_income = income_statements[
                'us-gaap_NetIncomeLoss',
                'Net Income'
            ]

        if not (operating_income := income_statements.get(['us-gaap_OperatingIncomeLoss',
                                                           'us-gaap_Revenues',
                                                           'Operating Income'])):

            operating_income = cash_flow['Net Operating Cash Flow']

        if ['us-gaap_Liabilities', 'Total Liabilities'] in balance_sheet:
            total_liabilities = balance_sheet['us-gaap_Liabilities', 'Total Liabilities']
        elif 'us-gaap_LiabilitiesNoncurrent' in balance_sheet:
            total_liabilities = balance_sheet['us-gaap_LiabilitiesCurrent'] + \
                balance_sheet['us-gaap_LiabilitiesNoncurrent']
        else:
            total_liabilities = sum((
                balance_sheet[key]
                for key in balance_sheet if ('LiabilitiesNoncurren' in key or 'DebtNoncurrent' in key)
            ))

        total_equity = total_assets + total_liabilities
        current_equity = current_assets + current_liabilities

        return cls(
            cash_and_cash_equivalents=cash_and_cash_equivalents,
            current_assets=current_assets,
            current_liabilities=current_liabilities,
            current_equity=current_equity,
            interest_expenses=interest_expenses,
            net_income=net_income,
            non_current_assets=total_assets - current_assets,
            non_current_liabilities=total_liabilities - current_liabilities,
            non_current_equity=total_equity - current_equity,
            operating_income=operating_income,
            shareholders_equity=shareholders_equity,
            total_assets=total_assets,
            total_liabilities=total_liabilities,
            total_equity=total_equity,
        )

    def export(self, commas=True) -> dict:
        return {
            key: value.partition('.')[0]
            for key, value in super().export(commas).items()
        }


@dataclass(frozen=True)
class LiquidityRatios(_Exportable):
    '''
    current_ratio: >-
        The current ratio measures a company’s ability to pay off short-term
        liabilities with current assets

    cash_ratio: >-
        The cash ratio measures a company’s ability to pay off short-term
        liabilities with cash and cash equivalents

    operating_cash_ratio: >-
        The operating cash flow ratio is a measure of the number of times a
        company can pay off current liabilities with the cash generated in a
        given period
    '''

    current_ratio: float
    cash_ratio: float
    operating_cash_ratio: float

    @classmethod
    def new(cls, facts: Facts):
        return cls(
            current_ratio=facts.current_assets / facts.current_liabilities,
            cash_ratio=facts.cash_and_cash_equivalents / facts.current_liabilities,
            operating_cash_ratio=facts.cash_and_cash_equivalents / facts.current_liabilities
        )


@dataclass(frozen=True)
class LeverageFinancialRatios(_Exportable):
    '''
    debt_ratio: >-
        The operating cash flow ratio is a measure of the number of times a
        company can pay off current liabilities with the cash generated in a
        given period

    debt_to_equity_ratio: >-
        The debt to equity ratio calculates the weight of total debt and
        financial liabilities against shareholders’ equity

    interest_coverage_ratio: >-
        The interest coverage ratio shows how easily a company can pay its
        interest expenses
    '''

    debt_ratio: float
    debt_to_equity_ratio: float
    interest_coverage_ratio: float

    @classmethod
    def new(cls, facts: Facts):

        try:
            interest_coverage_ratio = facts.operating_income / abs(facts.interest_expenses)
        except ZeroDivisionError:
            interest_coverage_ratio = float('inf')

        return cls(debt_ratio=facts.total_liabilities / facts.total_assets,
                   debt_to_equity_ratio=facts.total_liabilities / facts.shareholders_equity,
                   interest_coverage_ratio=interest_coverage_ratio)


@dataclass(frozen=True)
class ProfitabilityRatios(_Exportable):
    '''
    return_on_assets_ratio: >-
        The return on assets ratio measures how efficiently a company is using
        its assets to generate profit

    return_on_equity_ratio: >-
        The return on equity ratio measures how efficiently a company is using
        its equity to generate profit
    '''

    return_on_assets_ratio: float
    return_on_equity_ratio: float

    @classmethod
    def new(cls, facts: Facts):

        return cls(
            return_on_assets_ratio=facts.net_income / facts.total_assets,
            return_on_equity_ratio=facts.net_income / facts.shareholders_equity
        )


engine = Engine(
    loader=FileLoader(['templates']),
    extensions=[CoreExtension()]
)

#symbols = ('CDEV', 'MTDR', 'QEP', 'SM', 'NR', 'XOM', 'CVX', 'GEL', 'FET', 'CPE')
symbols = ('ABEPF', 'ARXRF', 'FTSSF', 'NMTLF', 'DCNNF', 'ALLIF', 'CCWOF', 'LTUM', 'FUSEF')
target = f'/home/pnaudus/Downloads/{datetime.date.today()} - Comparative analysis of {"-".join(symbols)}.html'
with open(target, 'w') as f:
    f.write(
        engine.get_template('template.html').render(dict(
            today=datetime.datetime.now().isoformat(),
            stocks={
                symbol: Stock(symbol, 'quarterly', 2020, 4).export()
                for symbol in symbols
            },
            historical={
                symbol: HistoricalStock(
                    symbol=symbol,
                    period='quarterly',
                    years=(2019, 2020),
                    quarters=(1, 2, 3, 4)
                ).export()
                for symbol in symbols
            },
            metadata=dict(
                symbols=symbols,
                report=Stock.export_meta()
            )
        ))
    )

print(f'Report written: {target}')
