import scrapy
import re

# from scrapy.shell import inspect_response


class LoopNetSpider(scrapy.Spider):
    name = 'loopnet'

    def start_requests(self):
        self.logger.info('Scraping listings for zip={}'.format(self.zip))
        yield scrapy.FormRequest(
            url='http://www.loopnet.com/search',
            formdata={'geography': self.zip, 'listingtypes': '1'},
            callback=self.parse,
        )

    def parse(self, response):
        for address in response.css('.listing-address'):
            _zip = address.css(
                'span[itemprop="postalCode"]::text').extract_first()
            if _zip != self.zip:
                self.logger.warning(
                    'Found listing with erroneous zip={}'.format(_zip))
                continue
            links = address.css('a')
            if len(links) != 1:
                self.logger.warning(
                    'Unexpected len(links)={} in address'.format(len(links)))
                continue
            yield response.follow(links[0], self.parse_detail)

    CSZ_REGEX = re.compile(r'(\w[^,]*),\s+(\w+)\s+(\d+)')

    def parse_detail(self, response):
        item = {}

        # HEADER - parse info above pics in div.property-info
        header = response.css('.property-info')
        city, state, _zip = self.CSZ_REGEX.search(
            header.css('.city-state::text').extract_first()).groups()
        if _zip != self.zip:
            return
        blurb = header.css('h2:not(.property-price)::text').extract_first()
        blurb = re.sub(r'\s+', ' ', blurb).strip()
        price = self._parse_int(
            header.css('.property-price::text').extract_first())
        item.update(
            address=header.css('h1::text').extract_first(),
            city=city,
            state=state,
            zip=_zip,
            blurb=blurb,
            price=price,
        )

        yield item

    PARSE_INT_REGEX = re.compile(r'[^.\d]')

    def _parse_int(self, s):
        return round(float(self.PARSE_INT_REGEX.sub('', s)))
