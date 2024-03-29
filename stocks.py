#!/usr/bin/python

import sys
from pprint import pprint
from datetime import datetime
from bs4 import BeautifulSoup
import requests

import ystockquote
from dateutil.relativedelta import relativedelta
from urllib2 import HTTPError

def ben_graham(eps, next_eps, bond_yield=4.24):
    """
    Gets, or tries to get, the intrinsic value of a stock based on it's ttm EPS and the corporate
    bond yield.
    """
    # growth_rate = (next_eps - eps) / eps
    # growth_rate *= 100
    growth_rate = next_eps

    # The top part of the fraction: EPS x (8.5 + 2g) x 4.4
    numerator = eps * (8.5 + (2 * growth_rate)) * 4.4
    iv = numerator / bond_yield

    return round(iv, 3)


def get_volatility(quote, days=70):
    """
    Get the volatility based on this fun formula from Brandon
    """
    today = datetime.today().strftime("%Y-%m-%d")
    fifty_ago = (datetime.today() - relativedelta(days=days)).strftime("%Y-%m-%d")
    
    try:
        prices = ystockquote.get_historical_prices(str(quote), fifty_ago, today)
    except HTTPError:
        return 0

    total = 0
    for d, p in prices.iteritems():
        numerator = float(p.get('High')) - float(p.get('Low'))
        total += numerator / float(p.get('Open'))

    volatility = round(total / len(prices), 4) * 100

    return volatility

def get_sp_500_list():
    """
    returns a list of the most recent s&p 500
    """
    # We are going to scrape this url
    url = "http://www.stockmarketsreview.com/companies_sp500/"

    soup = BeautifulSoup(requests.get(url).content)

    # It's the second table.
    table = soup.find_all('table')[1]
    rows = table.findAll('tr')

    symbols = []
    for i, row in enumerate(rows):
        if i:
            # If it's in the NYSE column
            if row.findAll('td')[2].string:
                symbols.append(row.findAll('td')[2].string)
            else:
                # Otherwise, it's in the NASDAQ column
                symbols.append(row.findAll('td')[3].string)

    return symbols

def process():
    hopefuls = []
    hopefuls_mind_pe = []
    undervalued_stocks = []
    ignore_dividend_stocks = []

    if sys.argv[1] == '500':
        quote_list = get_sp_500_list()
    else:
        quote_list = sys.argv[1:]

    for quote in quote_list:
        # Let's set up some basic criteria to see if this is a stock that
        # warrants further inspection. These will be boolean markers we'll flip on 
        # if it makes sense.
        DIVIDEND_YIELD = False  # Let's say we want this >= %1
        DESIRED_DIVIDEND_RATE = 1

        # Relative Intrinsic value
        RIV_RATIO = False  # Let's say we want this > 1.00
        DESIRED_RIV_RATE = 1

        VOLATILITY = False  # Let's say we want this > 2.0%
        DESIRED_VOLATILITY_RATE = 2

        PE_RATIO = False  # We want it at 15 or less.
        DESIRED_PE_RATIO = 15

        AAA_BOND_RATE = 3.96

        # First thing we want is some basic information on the quote.
        details = ystockquote.get_by_id_list(quote, [
            'p',  # 0 Previous close
            'l1',  # 1 Last trade price
            'o',  # 2 Today's open
            'w1',  # 3 Today's value change
            'e7',  # 4 EPS - Current year
            'e9',  # 5 EPS - Next year
            'r',  # 6 PE ratio
            'y',  # 7 Dividend yield
            'k5',  # 8 Percent from 52wk high
            'j6', # 9 Percent from 52wk low
            'n',  # 10 Name
        ])

        print ('Finding quote for %s (%s)' % (details[10], quote))

        # Set up some variables that are used throughout
        last_trade = float(details[1])

        print ('Prev Close: %s,' % details[0], 'Today Open: $%s,' % details[2], 'Last Trade: $%s,' % last_trade)
        print ('Today\'s Change: %s' % details[3].split(' ')[2].rstrip('"'))
        print ('%% from 52wk Low: %s,' % details[9], '%% from 52wk High: %s' % details[8])

        # Get the past ~50 BIZ days of trading.
        volatility = get_volatility(quote)
        print ('Volatility: %s%%' % (volatility))
        VOLATILITY = True if volatility > DESIRED_VOLATILITY_RATE else False

        # Get Ben grahams formula
        try:
            eps = float(details[4])
        except ValueError:
            # Likely returned N/A
            eps = 0
        try:
            next_eps = float(details[5])
        except ValueError:
            next_eps = 0

        # IV stands for Intrinsic Value.  What the stock is possibly really worth.
        iv = ben_graham(eps, next_eps, AAA_BOND_RATE)

        if iv != 0:
            # Get the relative intrinsic value, RIV
            riv = round(iv / last_trade, 4)
            print ('RIV: %s' % riv)  # We want RIV to be better than 1.00, which would mean it's undervalued.
            RIV_RATIO = True if riv > DESIRED_RIV_RATE else False
        else:
            riv = 0

        # Add to our list if applicable
        if riv > 1.0:
            undervalued_stocks.append(quote)

        # Check out the PE ratio.
        try:
            pe = float(details[6])
            print ('P/E ratio: %s' % pe)
            PE_RATIO = True if pe <= DESIRED_PE_RATIO else False
        except ValueError:
            pe = 'Check Research'
            pass

        # Check out the dividends on this babe
        try:
            div_yield = float(details[7])
            print ('Dividend yield: %s%%' % div_yield)
            DIVIDEND_YIELD = True if div_yield >= DESIRED_DIVIDEND_RATE else False 
        except ValueError:
            print ('Dividend yield: %s' % details[7])

        if DIVIDEND_YIELD and RIV_RATIO and VOLATILITY and PE_RATIO:
            print ('***** Check out: %s *****' % quote)
            hopefuls.append(quote)
        elif DIVIDEND_YIELD and RIV_RATIO and VOLATILITY:
            print ('***** Check out: %s, mind the PE (%s) *****' % (quote, pe))
            hopefuls_mind_pe.append(quote)
        elif RIV_RATIO and VOLATILITY:
            ignore_dividend_stocks.append(quote)

        print ('')

    print ('The hopefuls are:', str(hopefuls))
    print ('Hopeful, but mind the pe are:', str(hopefuls_mind_pe))
    print ('The undervalued stocks are:', str(undervalued_stocks))
    print ('Ignoring dividends, these warrant a look:', str(ignore_dividend_stocks))

if __name__ == '__main__':
    process()

