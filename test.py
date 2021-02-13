import datetime
import thingy.engine
import lxml.objectify
from mako.template import Template
from thingy.collections import Date

import logging
logging.basicConfig(level=logging.INFO)

reports = (
    #('CDEV', 'MTDR', 'QEP', 'SM', 'NR', 'XOM', 'CVX', 'GEL', 'FET', 'CPE'),
    ('ABEPF', 'ARXRF', 'FTSSF', 'NMTLF', 'DCNNF', 'ALLIF', 'CCWOF', 'LTUM', 'FUSEF'),
)

for symbols in reports:
    with open('thingy/engine.xml') as f:
        engine = thingy.engine.Engine(
            symbols=symbols,
            logic=lxml.objectify.fromstring(f.read()),
            template_engine=Template(filename='thingy/templates/template.html.mako')
        )

    engine.execute(
        period='quarterly',
        dates=[Date(year, quarter)
               for year in (2019, 2020)
               for quarter in (1, 2, 3, 4)]
    ).write(f'/home/pnaudus/Downloads/{datetime.date.today()} - Comparative analysis of {"-".join(engine.symbols)}.html')
