import httpx
import pytest
import respx

from nube_agent.api import MutationBlockedError, mutation_firewall, parse_json, request, to_json
from nube_agent.config import BASE_URL


class TestToJson:
    def test_dict(self):
        assert to_json({"a": 1}) == '{"a": 1}'

    def test_list(self):
        assert to_json([1, 2]) == "[1, 2]"

    def test_string_passthrough(self):
        assert to_json("already a string") == "already a string"

    def test_unicode(self):
        result = to_json({"name": "Remera Azul"})
        assert "Remera Azul" in result


class TestParseJson:
    def test_valid_object(self):
        assert parse_json('{"a": 1}') == {"a": 1}

    def test_valid_list(self):
        assert parse_json("[1, 2]") == [1, 2]

    def test_invalid(self):
        result = parse_json("not json", "test_field")
        assert isinstance(result, str)
        assert "Invalid JSON" in result
        assert "test_field" in result


class TestRequest:
    @respx.mock
    def test_get_200(self):
        url = f"{BASE_URL}/products"
        respx.get(url).respond(200, json=[{"id": 1, "name": "Test"}])
        result = request("GET", "/products")
        assert isinstance(result, list)
        assert result[0]["id"] == 1

    @respx.mock
    def test_post_201(self):
        url = f"{BASE_URL}/products"
        respx.post(url).respond(201, json={"id": 2, "name": "New"})
        result = request("POST", "/products", json_body={"name": "New"})
        assert isinstance(result, dict)
        assert result["id"] == 2

    @respx.mock
    def test_delete_204(self):
        url = f"{BASE_URL}/products/1"
        respx.delete(url).respond(204)
        result = request("DELETE", "/products/1")
        assert result["status"] == "success"

    @respx.mock
    def test_404_error(self):
        url = f"{BASE_URL}/products/999"
        respx.get(url).respond(404, json={"message": "Not Found"})
        result = request("GET", "/products/999")
        assert isinstance(result, str)
        assert "404" in result

    @respx.mock
    def test_429_retry(self):
        url = f"{BASE_URL}/products"
        route = respx.get(url)
        route.side_effect = [
            httpx.Response(429, headers={"Retry-After": "0"}),
            httpx.Response(200, json=[{"id": 1}]),
        ]
        result = request("GET", "/products")
        assert isinstance(result, list)
        assert route.call_count == 2

    @respx.mock
    def test_transport_error(self):
        url = f"{BASE_URL}/products"
        respx.get(url).mock(side_effect=httpx.ConnectError("Connection refused"))
        result = request("GET", "/products")
        assert isinstance(result, str)
        assert "HTTP error" in result

    @respx.mock
    def test_mutation_firewall_blocks_mutating_methods(self):
        url = f"{BASE_URL}/products/1"
        route = respx.put(url).respond(200, json={"id": 1})
        with mutation_firewall():
            with pytest.raises(MutationBlockedError):
                request("PUT", "/products/1", json_body={"published": False})
        assert route.call_count == 0
