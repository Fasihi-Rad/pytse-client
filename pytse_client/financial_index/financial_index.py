import functools
import pandas as pd

from typing import Optional, List, Dict
from bs4 import BeautifulSoup


from pytse_client import utils
from pytse_client import symbols_data
from pytse_client import tse_settings
from pytse_client.download import download_financial_indexes


class FinancialIndex:
    def __init__(self,
                 symbol: str,
                 index: Optional[str] = None
                 ):
        self._index: str = index or symbols_data.get_financial_index(symbol)
        self.symbol: str = symbol if index is None else self._index
        self._intraday_url: str = tse_settings\
            .TSE_FINANCIAL_INDEX_EXPORT_INTRADAY_DATA_ADDRESS\
            .format(self._index)

    @property
    def last_update(self):
        # زمان انتشار
        raw_html = self._financial_index_page_text
        soup = BeautifulSoup(raw_html, 'html.parser')
        before_update_time_td: BeautifulSoup = \
            soup.find_all("td", text="زمان انتشار")[0]
        update_time_td: BeautifulSoup =\
            before_update_time_td.find_next_siblings("td")[0]
        return pd.to_datetime(update_time_td.get_text()).strftime("%H:%M")

    @property
    def last_value(self):
        # آخرین مقدار شاخص
        raw_html = self._financial_index_page_text
        soup = BeautifulSoup(raw_html, 'html.parser')
        before_lastval_td: BeautifulSoup =\
            soup.find_all("td", text="آخرین مقدار شاخص")[0]
        lastval_td: BeautifulSoup =\
            before_lastval_td.find_next_siblings("td")[0]
        return float(lastval_td.get_text().replace(",", ""))

    @property
    def high(self):
        # بیشترین مقدار روز
        raw_html = self._financial_index_page_text
        soup = BeautifulSoup(raw_html, 'html.parser')
        before_high_td: BeautifulSoup =\
            soup.find_all("td", text="بیشترین مقدار روز")[0]
        high_td: BeautifulSoup =\
            before_high_td.find_next_siblings("td")[0]
        return high_td.get_text()

    @property
    def low(self):
        # کمترین مقدار روز
        raw_html = self._financial_index_page_text
        soup = BeautifulSoup(raw_html, 'html.parser')
        before_low_td: BeautifulSoup =\
            soup.find_all("td", text="کمترین مقدار روز")[0]
        low_td: BeautifulSoup =\
            before_low_td.find_next_siblings("td")[0]
        return low_td.get_text()

    @property
    @functools.lru_cache()
    def history(self):
        return download_financial_indexes(self.symbol,
                                          write_to_csv=False,
                                          include_jdate=True,
                                          )[self.symbol]

    def _get_contributing_symbols(self, raw_html: str):
        # شرکت های موجود در شاخص
        raw_html = self._financial_index_page_text
        soup = BeautifulSoup(raw_html, 'html.parser')
        before_contr_symbols: BeautifulSoup =\
            soup.find_all("div", text="شرکت های موجود در شاخص")[0]
        contr_symbols: BeautifulSoup =\
            before_contr_symbols.find_next_siblings("div")[0]
        _index_symbols = list(map(lambda x: x.a["href"].split("i=")[
                              1], contr_symbols.find_all("td")[::9]))
        _symbols = list(map(lambda x: x.get_text(),
                        contr_symbols.find_all("td")[::9]))
        _contr_symbols = list(zip(_index_symbols, _symbols))
        return [
            {
                "symbol": _contr_symbol[1],
                "index": _contr_symbol[0]
            } for _contr_symbol in _contr_symbols
        ]

    @property
    @functools.lru_cache()
    def contributing_symbols(self) -> List[Dict[str, str]]:
        return self._get_contributing_symbols(
            self._financial_index_page_text
        )

    @property
    def intraday_price(self) -> pd.DataFrame:
        raw_html = self._financial_index_page_text
        soup = BeautifulSoup(raw_html, 'html.parser')
        before_intraday_price: BeautifulSoup =\
            soup.find_all("div", text="سابقه شاخص روز جاری")[0]

        intraday_price: BeautifulSoup =\
            before_intraday_price.find_next_siblings("div")[0]
        intraday_price_ls = list(
            map(lambda bs: bs.get_text(), intraday_price.find_all("td"))
        )
        columns = ["time", "value", "change_percentage", "low", "high"]

        rows = self._get_rows(intraday_price_ls, len(columns))
        df = pd.DataFrame(rows, columns=columns)
        df = df.astype(
            {
                "value": float,
                "change_percentage": float,
                "low": float,
                "high": float
            },
            errors='raise'
        )

        df["time"] = pd.to_datetime(df["time"], format="%H:%M")\
            .dt.time
        df.set_index("time", inplace=True)
        return df

    @property
    def _financial_index_page_text(self):
        raw_html = utils.requests_retry_session()\
            .get(self._intraday_url, timeout=10).text
        return raw_html

    def _get_rows(self, intraday_price_ls, col_len):
        intraday_price_ls = list(
            map(lambda x: x.replace(",", ""), intraday_price_ls))
        intraday_price_ls = list(
            map(lambda x: x.replace("(", "-"), intraday_price_ls))
        intraday_price_ls = list(
            map(lambda x: x.replace(")", ""), intraday_price_ls))
        rows = [intraday_price_ls[i:i+5]
                for i in range(0, len(intraday_price_ls), col_len)]
        return rows
