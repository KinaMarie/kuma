from functools import partial

from django.conf import settings

from nose.tools import eq_
from pyquery import PyQuery as pq

from gallery.tests import image
from sumo.parser import (WikiParser, _buildImageParams, _getWikiLink,
                         get_object_fallback)
from sumo.tests import TestCase
from wiki.models import Document
from wiki.tests import document, revision


def pq_link(p, text):
    return pq(p.parse(text))('a')


def doc_rev_parser(content, title='Installing Firefox', parser_cls=WikiParser):
    p = parser_cls()
    d = document(title=title)
    d.save()
    r = revision(document=d, content=content, is_approved=True)
    r.save()
    return (d, r, p)


_buildImageParamsDefault = partial(_buildImageParams,
                                   locale=settings.WIKI_DEFAULT_LANGUAGE)


class TestWikiParser(TestCase):
    fixtures = ['users.json']

    def setUp(self):
        self.d, self.r, self.p = doc_rev_parser(
            'Test content', 'Installing Firefox')

    def test_get_object_fallback_empty(self):
        """get_object_fallback returns message when no objects."""
        # English does not exist
        obj = get_object_fallback(Document, 'A doc', 'en-US', '!')
        eq_('!', obj)

    def test_get_object_fallback_english(self):
        # Create the English document
        d = document(title='A doc')
        d.save()
        # Now it exists
        obj = get_object_fallback(Document, 'A doc', 'en-US', '!')
        eq_(d, obj)

    def test_get_object_fallback_from_french(self):
        # Create the English document
        d = document(title='A doc')
        d.save()
        # Returns English document for French
        obj = get_object_fallback(Document, 'A doc', 'fr', '!')
        eq_(d, obj)

    def test_get_object_fallback_french(self):
        # Create the French document
        fr_d = document(title='A doc', locale='fr')
        fr_d.save()
        obj = get_object_fallback(Document, 'A doc', 'fr', '!')
        eq_(fr_d, obj)

        # Also works when English exists
        d = document(title='A doc')
        d.save()
        obj = get_object_fallback(Document, 'A doc', 'fr', '!')
        eq_(fr_d, obj)

    def test_image_params_page(self):
        """_buildImageParams handles wiki pages."""
        items = ['page=Installing Firefox']
        params = _buildImageParamsDefault(items)
        eq_('/en-US/kb/installing-firefox', params['link'])

    def test_image_params_link(self):
        """_buildImageParams handles external links."""
        items = ['link=http://example.com']
        params = _buildImageParamsDefault(items)
        eq_('http://example.com', params['link'])

    def test_image_params_page_link(self):
        """_buildImageParams - wiki page overrides link."""
        items = ['page=Installing Firefox', 'link=http://example.com']
        params = _buildImageParamsDefault(items)
        eq_('/en-US/kb/installing-firefox', params['link'])

    def test_image_params_align(self):
        """Align valid options."""
        align_vals = ('none', 'left', 'center', 'right')
        for align in align_vals:
            items = ['align=' + align]
            params = _buildImageParamsDefault(items)
            eq_(align, params['align'])

    def test_image_params_align_invalid(self):
        """Align invalid options."""
        items = ['align=zzz']
        params = _buildImageParamsDefault(items)
        assert not 'align' in params, 'Align is present in params'

    def test_image_params_valign(self):
        """Vertical align valid options."""
        valign_vals = ('baseline', 'sub', 'super', 'top', 'text-top',
                       'middle', 'bottom', 'text-bottom')
        for valign in valign_vals:
            items = ['valign=' + valign]
            params = _buildImageParamsDefault(items)
            eq_(valign, params['valign'])

    def test_image_params_valign_invalid(self):
        """Vertical align invalid options."""
        items = ['valign=zzz']
        params = _buildImageParamsDefault(items)
        assert not 'valign' in params, 'Vertical align is present in params'

    def test_image_params_alt(self):
        """Image alt override."""
        items = ['alt=some alternative text']
        params = _buildImageParamsDefault(items)
        eq_('some alternative text', params['alt'])

    def test_image_params_frameless(self):
        """Frameless image."""
        items = ['frameless']
        params = _buildImageParamsDefault(items)
        eq_(True, params['frameless'])

    def test_image_params_width_height(self):
        """Image width."""
        items = ['width=10', 'height=20']
        params = _buildImageParamsDefault(items)
        eq_('10', params['width'])
        eq_('20', params['height'])

    def test_get_wiki_link(self):
        """Wiki links are properly built for existing pages."""
        eq_('/en-US/kb/installing-firefox',
            _getWikiLink('Installing Firefox',
                         locale=settings.WIKI_DEFAULT_LANGUAGE))

    def test_showfor(self):
        """<showfor> tags should be escaped, not obeyed."""
        eq_('<p>&lt;showfor&gt;smoo&lt;/showfor&gt;</p>',
            self.p.parse('<showfor>smoo</showfor>').replace('\n', ''))


class TestWikiInternalLinks(TestCase):
    fixtures = ['users.json']

    def setUp(self):
        self.d, self.r, self.p = doc_rev_parser(
            'Test content', 'Installing Firefox')

    def test_simple(self):
        """Simple internal link markup."""
        link = pq_link(self.p, '[[Installing Firefox]]')
        eq_('/en-US/kb/installing-firefox', link.attr('href'))
        eq_('Installing Firefox', link.text())

    def test_simple_markup(self):
        text = '[[Installing Firefox]]'
        eq_('<p><a href="/en-US/kb/installing-firefox" rel="nofollow">' +
            'Installing Firefox</a></p>',
            self.p.parse(text).replace('\n', ''))

    def test_link_hash(self):
        """Internal link with hash."""
        link = pq_link(self.p, '[[Installing Firefox#section name]]')
        eq_('/en-US/kb/installing-firefox#section_name', link.attr('href'))
        eq_('Installing Firefox#section name', link.text())

    def test_link_hash_markup(self):
        """Internal link with hash."""
        text = '[[Installing Firefox#section name]]'
        eq_('<p><a href="/en-US/kb/installing-firefox#section_name"' +
                ' rel="nofollow">Installing Firefox#section name</a></p>',
            self.p.parse(text).replace('\n', ''))

    def test_hash_only(self):
        """Internal hash only."""
        link = pq_link(self.p, '[[#section 3]]')
        eq_('#section_3', link.attr('href'))
        eq_('#section 3', link.text())

    def test_link_name(self):
        """Internal link with name."""
        link = pq_link(self.p, '[[Installing Firefox|this name]]')
        eq_('/en-US/kb/installing-firefox', link.attr('href'))
        eq_('this name', link.text())

    def test_link_with_extra_pipe(self):
        link = pq_link(self.p, '[[Installing Firefox|with|pipe]]')
        eq_('/en-US/kb/installing-firefox', link.attr('href'))
        eq_('with|pipe', link.text())

    def test_hash_name(self):
        """Internal hash with name."""
        link = pq_link(self.p, '[[#section 3|this name]]')
        eq_('#section_3', link.attr('href'))
        eq_('this name', link.text())

    def test_link_hash_name(self):
        """Internal link with hash and name."""
        link = pq_link(self.p, '[[Installing Firefox#section 3|this name]]')
        eq_('/en-US/kb/installing-firefox#section_3', link.attr('href'))
        eq_('this name', link.text())

    def test_link_hash_name_markup(self):
        """Internal link with hash and name."""
        text = '[[Installing Firefox#section 3|this name]]'
        eq_('<p><a href="/en-US/kb/installing-firefox#section_3"' +
            ' rel="nofollow">this name</a>\n</p>', self.p.parse(text))

    def test_simple_create(self):
        """Simple link for inexistent page."""
        link = pq_link(self.p, '[[A new page]]')
        eq_('/kb/new?title=A+new+page', link.attr('href'))
        eq_('A new page', link.text())

    def test_link_edit_hash_name(self):
        """Internal link for inexistent page with hash and name."""
        link = pq_link(self.p, '[[A new page#section 3|this name]]')
        eq_('/kb/new?title=A+new+page#section_3', link.attr('href'))
        eq_('this name', link.text())


def pq_img(p, text, selector='div.img', locale=settings.WIKI_DEFAULT_LANGUAGE):
    doc = pq(p.parse(text, locale=locale))
    return doc(selector)


class TestWikiImageTags(TestCase):
    fixtures = ['users.json']

    def setUp(self):
        self.d, self.r, self.p = doc_rev_parser(
            'Test content', 'Installing Firefox')
        self.img = image(title='test.jpg')

    def tearDown(self):
        self.img.delete()

    def test_empty(self):
        """Empty image tag markup does not change."""
        img = pq_img(self.p, '[[Image:]]', 'p')
        eq_('The image "" does not exist.', img.text())

    def test_simple(self):
        """Simple image tag markup."""
        img = pq_img(self.p, '[[Image:test.jpg]]', 'img')
        eq_('test.jpg', img.attr('alt'))
        eq_(self.img.file.url, img.attr('src'))

    def test_simple_fallback(self):
        """Fallback to English if current locale doesn't have the image."""
        img = pq_img(self.p, '[[Image:test.jpg]]', selector='img', locale='ja')
        eq_('test.jpg', img.attr('alt'))
        eq_(self.img.file.url, img.attr('src'))

    def test_full_fallback(self):
        """Find current locale's image, not the English one."""
        # first, pretend there is no English version
        self.img.locale = 'ja'
        self.img.save()
        img = pq_img(self.p, '[[Image:test.jpg]]', selector='img', locale='ja')
        eq_('test.jpg', img.attr('alt'))
        eq_(self.img.file.url, img.attr('src'))

        # then, create an English version
        en_img = image(title='test.jpg')
        # Ensure they're not equal
        self.assertNotEquals(en_img.file.url, self.img.file.url)

        # make sure there is no fallback
        img = pq_img(self.p, '[[Image:test.jpg]]', selector='img', locale='ja')
        eq_('test.jpg', img.attr('alt'))
        eq_(self.img.file.url, img.attr('src'))

        # now delete the English version
        self.img.delete()
        self.img = en_img  # don't break tearDown
        img = pq_img(self.p, '[[Image:test.jpg]]', selector='img', locale='ja')
        eq_('test.jpg', img.attr('alt'))
        eq_(self.img.file.url, img.attr('src'))

    def test_caption(self):
        """Give the image a caption."""
        self.img.title = 'img test.jpg'
        self.img.save()
        img_div = pq_img(self.p, '[[Image:img test.jpg|my caption]]')
        img = img_div('img')
        caption = img_div.text()

        eq_(self.img.file.url, img.attr('src'))
        eq_('my caption', img.attr('alt'))
        eq_('my caption', caption)

    def test_page_link(self):
        """Link to a wiki page."""
        img_div = pq_img(self.p, '[[Image:test.jpg|page=Installing Firefox]]')
        img_a = img_div('a')
        img = img_a('img')
        caption = img_div.text()

        eq_('test.jpg', img.attr('alt'))
        eq_('test.jpg', caption)
        eq_(self.img.file.url, img.attr('src'))
        eq_('/en-US/kb/installing-firefox', img_a.attr('href'))

    def test_page_link_edit(self):
        """Link to a nonexistent wiki page."""
        img_div = pq_img(self.p, '[[Image:test.jpg|page=Article List]]')
        img_a = img_div('a')
        img = img_a('img')
        caption = img_div.text()

        eq_('test.jpg', img.attr('alt'))
        eq_('test.jpg', caption)
        eq_(self.img.file.url, img.attr('src'))
        eq_('/kb/new?title=Article+List', img_a.attr('href'))

    def test_page_link_caption(self):
        """Link to a wiki page with caption."""
        img_div = pq_img(self.p,
                         '[[Image:test.jpg|page=Article List|my caption]]')
        img_a = img_div('a')
        img = img_a('img')
        caption = img_div.text()

        eq_('my caption', img.attr('alt'))
        eq_('my caption', caption)
        eq_(self.img.file.url, img.attr('src'))
        eq_('/kb/new?title=Article+List', img_a.attr('href'))

    def test_link(self):
        """Link to an external page."""
        img_div = pq_img(self.p, '[[Image:test.jpg|link=http://example.com]]')
        img_a = img_div('a')
        img = img_a('img')
        caption = img_div.text()

        eq_('test.jpg', img.attr('alt'))
        eq_('test.jpg', caption)
        eq_(self.img.file.url, img.attr('src'))
        eq_('http://example.com', img_a.attr('href'))

    def test_link_caption(self):
        """Link to an external page with caption."""
        img_div = pq_img(self.p,
                         '[[Image:test.jpg|link=http://example.com|caption]]')
        img_a = img_div('a')
        img = img_div('img')
        caption = img_div.text()

        eq_('caption', img.attr('alt'))
        eq_('caption', caption)
        eq_(self.img.file.url, img.attr('src'))
        eq_('http://example.com', img_a.attr('href'))

    def test_link_align(self):
        """Link with align."""
        img_div = pq_img(self.p,
                  '[[Image:test.jpg|link=http://site.com|align=left]]')
        eq_('img align-left', img_div.attr('class'))

    def test_link_align_invalid(self):
        """Link with invalid align."""
        img_div = pq_img(self.p,
                         '[[Image:test.jpg|link=http://example.ro|align=inv]]')
        eq_('img', img_div.attr('class'))

    def test_link_valign(self):
        """Link with valign."""
        img = pq_img(
            self.p,
            '[[Image:test.jpg|link=http://example.com|valign=top]]', 'img')
        eq_('vertical-align: top;', img.attr('style'))

    def test_link_valign_invalid(self):
        """Link with invalid valign."""
        img = pq_img(
            self.p,
            '[[Image:test.jpg|link=http://example.com|valign=off]]', 'img')
        eq_(None, img.attr('style'))

    def test_alt(self):
        """Image alt attribute is overriden but caption is not."""
        img_div = pq_img(self.p, '[[Image:test.jpg|alt=my alt|my caption]]')
        img = img_div('img')
        caption = img_div.text()

        eq_('my alt', img.attr('alt'))
        eq_('my caption', caption)

    def test_alt_empty(self):
        """Image alt attribute can be empty."""
        img = pq_img(self.p, '[[Image:test.jpg|alt=|my caption]]', 'img')

        eq_('', img.attr('alt'))

    def test_alt_unsafe(self):
        """Potentially unsafe alt content is escaped."""
        unsafe_vals = (
            ('an"<script>alert()</script>',
             'an&quot;&amp;lt;script&amp;gt;alert()&amp;lt;/script&amp;gt;'),
            ("an'<script>alert()</script>",
             "an'&amp;lt;script&amp;gt;alert()&amp;lt;/script&amp;gt;"),
            ('single\'"double',
             "single'&quot;double"),
        )
        for alt_sent, alt_expected in unsafe_vals:
            img_div = pq_img(self.p, '[[Image:test.jpg|alt=' + alt_sent + ']]')
            img = img_div('img')

            is_true = str(img).startswith('<img alt="' + alt_expected + '"')
            assert is_true, ('Expected "%s", sent "%s"' %
                             (alt_expected, alt_sent))

    def test_width(self):
        """Image width attribute set."""
        img_div = pq_img(self.p, '[[Image:test.jpg|width=10]]')
        img = img_div('img')

        eq_('10', img.attr('width'))

    def test_width_invalid(self):
        """Invalid image width attribute set to auto."""
        img_div = pq_img(self.p, '[[Image:test.jpg|width=invalid]]')
        img = img_div('img')

        eq_(None, img.attr('width'))

    def test_height(self):
        """Image height attribute set."""
        img_div = pq_img(self.p, '[[Image:test.jpg|height=10]]')
        img = img_div('img')

        eq_('10', img.attr('height'))

    def test_height_invalid(self):
        """Invalid image height attribute set to auto."""
        img_div = pq_img(self.p, '[[Image:test.jpg|height=invalid]]')
        img = img_div('img')

        eq_(None, img.attr('height'))

    def test_frameless(self):
        """Image container has frameless class if specified."""
        img = pq_img(self.p, '[[Image:test.jpg|frameless|caption]]', 'img')
        eq_('frameless', img.attr('class'))
        eq_('caption', img.attr('alt'))
        eq_(self.img.file.url, img.attr('src'))

    def test_frameless_link(self):
        """Image container has frameless class and link if specified."""
        img_a = pq_img(self.p,
                       '[[Image:test.jpg|frameless|page=Installing Firefox]]',
                       'a')
        img = img_a('img')
        eq_('frameless', img.attr('class'))
        eq_('/en-US/kb/installing-firefox', img_a.attr('href'))
