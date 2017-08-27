import scrapy
import re
import sys

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

        for a in response.css('.paging a.caret-right-large'):
            yield response.follow(a, self.parse)

    SECTION_SELECTORS = [
        '.property-info',
        '.property-details',
        '.description',
        '.highlights',
    ]

    def parse_detail(self, response):
        item = {'url': response.url}

        for selector in self.SECTION_SELECTORS:
            selection = response.css(selector)
            fname = 'parse_' + selector[1:].replace('-', '_')

            try:
                item.update(getattr(self, fname)(selection))
            except:
                self.logger.warn(
                    'Unexpected error while parsing {} section: {}'
                    .format(selector, sys.exc_info()[0]))

        yield item

    CSZ_REGEX = re.compile(r'(\w[^,]*),\s+(\w+)\s+(\d+)')

    def parse_property_info(self, section):
        city, state, _zip = self.CSZ_REGEX.search(
            section.css('.city-state::text').extract_first()).groups()
        if _zip != self.zip:
            return
        blurb = section.css('h2:not(.property-price)::text').extract_first()
        blurb = re.sub(r'\s+', ' ', blurb).strip()
        price = self._parse_int(
            section.css('.property-price::text').extract_first())
        return {
            'address': section.css('h1::text').extract_first(),
            'city': city,
            'state': state,
            'zip': _zip,
            'blurb': blurb,
            'price': price,
        }

    def parse_property_details(self, section):
        tds = [
            self._parse_td(td)
            for td in section.css('.property-data td').extract()
        ]
        props = {k: v for k, v in dict(zip(tds[::2], tds[1::2])).items() if k}
        props['name'] = section.css('.listing-name::text').extract_first()
        keys = [
            k.replace(':', '')
            for k in section.css('.property-timestamp span::text').extract()
        ]
        values = [
            v.strip()
            for v in section.css('.property-timestamp td::text').extract()
        ]
        props.update({k: v for k, v in dict(zip(keys, values)).items() if k})
        return props

    def parse_description(self, section):
        description = '\n'.join(section.css('.column-12 p::text').extract())
        return {'description': description}

    def parse_highlights(self, sections):
        props = {}
        for section in sections:
            key = section.css('h3::text').extract_first()
            value = '\n'.join(section.css('li::text').extract())
            if key:
                props[key] = value
        return props

    PARSE_INT_REGEX = re.compile(r'[^.\d]')

    def _parse_int(self, s):
        try:
            return round(float(self.PARSE_INT_REGEX.sub('', s)))
        except (ValueError, TypeError):
            self.logger.warn('Could not parse int from "{}"'.format(s))
            return None

    PARSE_TD_REGEX = re.compile(r'<td>(.*)</td>')

    def _parse_td(self, s):
        s = ''.join(s.split())
        m = self.PARSE_TD_REGEX.search(s)
        return m and m.group(1)
