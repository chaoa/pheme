# -*- coding: utf-8 -*-
# tests/test_report_generation.py
# Copyright (C) 2020 Greenbone Networks GmbH
#
# SPDX-License-Identifier: AGPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from unittest.mock import patch
from typing import List
import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient

from pheme.datalink import as_datalink
from pheme.settings import SECRET_KEY
from tests.generate_test_data import gen_report


def generate(prefix: str, amount: int) -> List[str]:
    return ["{}_{}".format(prefix, i) for i in range(amount)]


def test_report_contains_equipment():
    client = APIClient()
    url = reverse('transform')
    report = {
        'report': {
            'report': gen_report(generate('host', 10), generate('oid', 5))
        }
    }
    response = client.post(url, data=report, format='xml')
    assert response.status_code == 200
    result = cache.get(response.data)
    assert result['results'][0]['equipment']['os'] == "rusty rust rust"
    assert result['results'][0]['equipment']['ports'] is not None


def test_report_contains_charts():
    client = APIClient()
    url = reverse('transform')
    report = {
        'report': {
            'report': gen_report(generate('host', 10), generate('oid', 5))
        }
    }
    response = client.post(url, data=report, format='xml')
    assert response.status_code == 200
    result = cache.get(response.data)
    assert result['overview'] is not None
    assert result['overview']['hosts'] is not None
    assert result['overview']['nvts'] is not None
    # assert result['overview']['vulnerable_equipment'] is not None


@pytest.mark.parametrize(
    "http_accept",
    [
        "application/pdf",
        "text/html",
    ],
)
def test_http_accept_visual(http_accept):
    subtype = http_accept.split('/')[-1]
    css_key = 'vulnerability_report_{}_css'.format(subtype)
    template_key = 'vulnerability_report_{}_template'.format(subtype)
    client = APIClient()
    url = reverse(
        'put_parameter',
    )
    # api_key = request.META.get('HTTP_X_API_KEY', "")
    response = client.put(
        url,
        data={
            css_key: "html { background: #000; }",
            template_key: "<html><h1>Holla</h1></html>",
        },
        HTTP_X_API_KEY=SECRET_KEY,
    )
    assert response.status_code == 200
    test_http_accept(http_accept)


@pytest.mark.parametrize(
    "http_accept",
    [
        "application/json",
        "application/xml",
        "text/csv",
    ],
)
def test_http_accept(http_accept):
    url = reverse('transform')
    report = {
        'report': {
            'report': gen_report(
                generate('host', 1),
                generate('oid', 1),
                name='http_accept_test',
            )
        }
    }
    client = APIClient()
    response = client.post(url, data=report, format='xml')
    assert response.status_code == 200
    key = response.data
    report_url = reverse('report', kwargs={'name': key})
    html_report = client.get(report_url, HTTP_ACCEPT=http_accept)
    assert html_report.status_code == 200
    return html_report


def test_generate_format_editor_html_report():
    def upload(key, data):
        cache_url = reverse('store_cache')
        to_send = {"key": key, "value": data}
        response = APIClient().post(cache_url, data=to_send, format='json')
        assert response.status_code == 200

    def upload_image(key, name, content):
        cache_url = reverse('store_cache')
        to_send = {
            "key": key,
            "value": {
                "name": name,
                "content": content,
            },
            "append": True,
        }
        response = APIClient().post(
            cache_url + '?append_image=true', data=to_send, format='json'
        )
        assert response.status_code == 200

    images = [
        as_datalink("p1".encode(), "png"),
        as_datalink("p2".encode(), "jpg"),
    ]
    client = APIClient()
    url = reverse('transform')
    report = {
        'report': {
            'report': gen_report(
                generate('host', 10),
                generate('oid', 5),
                name='report_format_editor_test',
            )
        }
    }
    response = client.post(url, data=report, format='xml')
    assert response.status_code == 200
    key = response.data
    report_url = reverse('report', kwargs={'name': key})
    html_template = """
        <html>
            <head>
                <style>{{ css }}</style>
            </head>
            <body>
            <p>{{ name }}</p>
            <img src="{{ images.0 }}"/>
            <img src="{{ images.1 }}"/>
            </body>
            </html>
        """
    html_css = "body { background-color: #000; }"
    for i, content in enumerate(images):
        upload_image("{}images".format(key), str(i), content)
    upload("{}html_template".format(key), html_template)
    upload("{}html_css".format(key), html_css)
    # upload(images)
    html_report = client.get(
        report_url, HTTP_ACCEPT='text/html+report_format_editor'
    )
    assert html_report.status_code == 200
    report = str(html_report.getvalue())
    assert 'report_format_editor_test' in report
    assert 'background-color: #000' in report
    for content in images:
        assert "<img src=\"{}\"/>".format(content) in report


@patch('pheme.parameter.pheme.authentication.get_username_role')
def test_html_report_contains_user_paramater(user_information):
    user_information.side_effect = [(None, None), ('test', 'admin')]
    subtype = "html"
    css_key = 'vulnerability_report_{}_css'.format(subtype)
    template_key = 'vulnerability_report_{}_template'.format(subtype)
    client = APIClient()
    url = reverse(
        'put_parameter',
    )
    html_template = "<html><body><p>{{ main_color }}</p></body></html>" ""
    response = client.put(
        url,
        data={
            css_key: "html { background: {{ main_color }}; }",
            template_key: html_template,
            "main_color": "#fff",
        },
        HTTP_X_API_KEY=SECRET_KEY,
    )
    assert response.status_code == 200
    assert response.data['main_color']
    client = APIClient()
    url = reverse(
        'put_value_parameters',
        kwargs={"key": "main_color"},
    )
    response = client.put(url, data="#000", format='json')
    assert response.status_code == 200
    assert response.data['user_specific']['test']['main_color'] == "#000"
    report_response = test_http_accept('text/html')
    html_report = report_response.getvalue().decode('utf-8')
    assert html_report == "<html><body><p>#fff</p></body></html>"
