from __future__ import annotations
import itertools
import yaml
import xmltodict
import lxml.etree
import mako.exceptions
from typing import Union, List, Dict, Any
from thingy.edgar.stock import Stock as EdgarStock
from thingy.edgar.filing import Filing as EdgarFiling
from thingy.market_watch import Stock as MarketWatchStock
from thingy.market_watch import Filing as MarketWatchFiling
from dataclasses import dataclass
from transitions.core import EventData
from lxml.objectify import ObjectifiedElement
from icecream import ic
from collections import defaultdict
from thingy.collections import FallThruDict
from thingy.collections import Report, Date
from thingy.state import State, DeferredEval, ResultKey
from thingy.metric_handlers import Fact, Ratio
from transitions.extensions import HierarchicalMachine as Machine
from mako.template import Template


class Engine(Machine):
    def __init__(self, symbols: List[str], logic: ObjectifiedElement, template_engine: Template):
        self.context = State()
        self.symbols = symbols
        self.logic = logic
        self.template_engine = template_engine
        super().__init__(
            send_event=True,
            **xmltodict.parse(
                lxml.etree.tostring(
                    logic.machine
                )
            )['machine']
        )

    def execute(self, dates: List[Date], period: str = 'annual') -> Engine:
        dates = sorted(dates)
        ic(dates)
        self.START(period=period, dates=dates)

        for group in itertools.chain(self.logic.facts.groups.group,
                                     self.logic.ratios.groups.group):
            self.GROUP(group=group)

        for symbol in self.context.metadata.symbols:
            self.SYMBOL(symbol=symbol)

            for date in dates:
                self.DATE(date=date)

                for fact in self.logic.facts.fact:
                    self.FACT(fact=fact)
                    if hasattr(fact, 'eval'):
                        self.EVAL(eval=fact.eval)
                    if hasattr(fact, 'query'):
                        for query in fact.query:
                            self.QUERY(query=query)

                for ratio in self.logic.ratios.ratio:
                    self.RATIO(ratio=ratio)
        self.END()

        return self

    def write(self, target: str):
        if not self.context:
            raise RuntimeError('execute() must be run before write()')
        with open(target, 'w') as f:
            try:
                f.write(
                    self.template_engine.render(
                        ResultKey=ResultKey,
                        **self.context.to_dict()
                    )
                )
            except BaseException:
                ic(mako.exceptions.text_error_template().render())
                raise

    # -------------------------------------------------
    # State handlers

    def on_enter_Starting(self, event: EventData):
        '''Clear and re-initialize state'''
        del self.context
        self.context = State()
        self.context.metadata.symbols = self.symbols
        self.context.period = event.kwargs['period']
        self.context.metadata.dates = event.kwargs['dates']

    def on_enter_ProcessingGroup_Fact(self, event: EventData):
        group = event.kwargs['group']
        result = [Fact(fact) for fact in self.logic.facts.fact
                  if fact.get('group') == group.get('id')]
        self.context.metadata.facts[str(group)] = result

    def on_enter_ProcessingGroup_Ratio(self, event: EventData):
        group = event.kwargs['group']
        result = [Ratio(ratio) for ratio in self.logic.ratios.ratio
                  if ratio.get('group') == group.get('id')]
        self.context.metadata.ratios[str(group)] = result

    def on_enter_ProcessingSymbol(self, event: EventData):
        '''Store state for future use.'''
        self.context.symbol = event.kwargs['symbol']

    def on_enter_ProcessingSymbol_Date(self, event: EventData):
        '''Store date for future use and get associated filing'''
        self.context.date = event.kwargs['date']

        if len(self.context.symbol) <= 4:
            stock = EdgarStock(self.context.symbol)
        else:
            stock = MarketWatchStock(self.context.symbol)

        filing = stock.get_filing(self.context.period,
                                  self.context.date.year,
                                  self.context.date.quarter)

        self.context.report = Report.new(filing)

    def on_exit_ProcessingSymbol_Date(self, event: EventData):
        '''Perform cleanup and validation.'''
        del self.context.report
        self.context.report = None

        if self.context.deferred_evals:
            ic(self.context)
            ic(self.context.deferred_evals)
            raise ValueError('Not all deferred evals have been computed')

        missing = set(fact.get('id') for fact in self.logic.facts.fact) - set(self.context.current_result.facts)
        if missing:
            ic(missing)
            raise ValueError('Not all facts have data')

        missing = set(ratio.get('id') for ratio in self.logic.ratios.ratio) - set(self.context.current_result.ratios)
        if missing:
            ic(missing)
            raise ValueError('Not all ratios have data')

    def on_enter_ProcessingSymbol_Date_Fact(self, event: EventData):
        fact = Fact(event.kwargs['fact'])
        self.context.fact = fact

    def on_exit_ProcessingSymbol_Date_Fact(self, event: EventData):
        # Try to re-process deferred evals
        deferred_evals = list(self.context.deferred_evals)  # Make a local copy
        self.context.deferred_evals.clear()

        for spec in deferred_evals:
            self.EVAL(fact=spec.fact, eval=spec.eval)

        deferred_facts = {deferred.fact.id for deferred in self.context.deferred_evals}

        # Make sure that the fact has a proper value
        if self.context.current_result.facts.get(self.context.fact.id) is None:
            # Perhaps it was just deferred?
            if self.context.fact.id not in deferred_facts:
                ic(self.context.symbol)
                ic(self.context.current_result.facts)
                ic(self.context.fact.id)
                ic(deferred_facts)
                raise ValueError('No value computed for fact')

    def on_enter_ProcessingSymbol_Date_Fact_DeferredEval(self, event: EventData):
        self.context.deferred_evals.append(DeferredEval(
            fact=self.context.fact,
            eval=event.kwargs['eval']
        ))

    def on_enter_ProcessingSymbol_Date_Fact_Eval(self, event: EventData):
        # If a fact has been pasesed in, use that. Else, just use the current fact
        fact = event.kwargs.get('fact', self.context.fact)
        eval = str(event.kwargs['eval'])
        fact_context = self.context.current_result.facts
        result = fact.execute_eval(eval=eval, fact_context=fact_context)
        fact_context[fact.id] = result

    def on_enter_ProcessingSymbol_Date_Fact_Query(self, event: EventData):
        if self.context.fact.id in self.context.current_result.facts:
            return  # Don't compute a new value if we already have one

        result = self.context.fact.execute_query(event.kwargs['query'], self.context.report)

        if result is not None:
            # Don't save None values
            self.context.current_result.facts[self.context.fact.id] = result

    def on_enter_ProcessingSymbol_Date_Ratio(self, event: EventData):
        ratio = event.kwargs['ratio']
        result = Ratio.calculate_ratio(ratio, self.context.current_result.facts)
        self.context.current_result.ratios[ratio.get('id')] = result

    # -------------------------------------------------
    # Edge Methods

    def fact_eval_has_prerequisites(self, event: EventData) -> bool:
        return self.context.fact.eval_has_prerequisites(
            eval=event.kwargs['eval'],
            fact_context=self.context.current_result.facts
        )

    def group_is_fact_group(self, event: EventData) -> bool:
        ic(event)
        return event.kwargs['group'].getparent().getparent().tag == 'facts'
