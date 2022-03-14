import sqlalchemy
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options 
import datetime
import json
import time


def state_seats(settings, driver):
    data = []

    for state, link in settings['StateLinks'].items():
        driver.get(link)

        #loop over accordians
        for accordion in driver.find_elements_by_xpath("//*[contains(@data-automation-id, 'market-item')]"):
            #grab the elecorate name
            header = accordion.find_element_by_xpath(".//*[@class='size14_f7opyze bold_f1au7gae']").text

            #check if electorate should be rechecked
            if last_run_check(header, settings['SeatChecks'][header]):
                #click Show All
                accordion.find_element_by_xpath(".//*[@class='size14_f7opyze Endeavour_fhudrb0 normal_fgzdi7m' and text()='Show All']").click()
                
                #get party and price data
                parties = accordion.find_elements_by_xpath(".//*[@class='size14_f7opyze outcomeName_f19a8l1b']")
                prices = accordion.find_elements_by_xpath(".//*[@class='size14_f7opyze bold_f1au7gae priceTextSize_frw9zm9']")
                
                #loop over data and send to list
                for p, x in zip(parties, prices):
                    data.append([header, state, p.text, x.text, get_now()])

            if data:
                _df = pd.DataFrame(data, columns=['electorate','state','party','price','capture_time']).set_index('electorate')

                engine = get_engine()
                _df.to_sql('state_data', engine, if_exists='append', index=True)

                engine.dispose()


def federal_odds(settings, driver):
    if last_run_check('Federal', settings['FederalCheck']):
        data = []
        parties = []
        
        driver.get(settings['FederalLink'])

        #NOTE: elements have inconsistent shapes hence the workaround to remove Filter from parties below
        _parties = driver.find_elements_by_xpath("//*[@class='size12_fq5j3k2']")
        prices = driver.find_elements_by_xpath("//*[@class='size14_f7opyze bold_f1au7gae priceTextSize_frw9zm9']")

        for p in _parties:
            if p.text != 'Filter':
                parties.append(p.text)

        for p, x in zip(parties, prices):
            data.append([p, x.text, get_now()])

        if data:
            _df = pd.DataFrame(data, columns=['party','price','capture_time']).set_index('party')

            engine = get_engine()
            _df.to_sql('federal_data', engine, if_exists='append', index=True)

            engine.dispose()


def get_driver():
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    return webdriver.Chrome(options=options)


def get_now():
     return datetime.datetime.now().strftime('%Y-%m-%d %H:%M')


def get_engine():
    return sqlalchemy.create_engine('sqlite:///./federal_election.db')


def get_settings():
    """ Returns the settings json """
    with open('./settings.json', 'rb') as f:
        return json.load(f)


def last_run_check(seat, time_check):
    try:
        engine = get_engine()

        if seat == 'Daily':
            last_run = engine.execute("""SELECT MAX(capture_time) FROM state_data """).fetchone()[0]
        elif seat == 'Federal':
            last_run = engine.execute("""SELECT MAX(capture_time) FROM federal_data """).fetchone()[0]
        else:
            last_run = engine.execute(f"""SELECT MAX(capture_time) FROM state_data WHERE electorate = '{seat}' """).fetchone()[0]

        fmt = '%Y-%m-%d %H:%M'
        now = datetime.datetime.strptime(get_now(), fmt)
        last_run = datetime.datetime.strptime(last_run, fmt)

        d1 = time.mktime(last_run.timetuple())
        d2 = time.mktime(now.timetuple())

        diff = int((d2 - d1) / 60)

        if diff > (time_check * 60):
            return True
    finally:
        engine.dispose()


if __name__ == '__main__':
    while True:
        settings = get_settings()
        if settings['DailyCheck']:
            run_data = last_run_check('Daily', 24)

        if not settings['DailyCheck'] or run_data:
            driver = get_driver()
            state_seats(settings, driver)
            federal_odds(settings, driver)

        time.sleep(30 * 60)