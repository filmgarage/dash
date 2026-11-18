import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from errors import ApiError  # noqa: E402
from ha import MAX_PICTURE_BYTES, Supervisor, picture_path_allowed  # noqa: E402


class NoNetwork:
    """A session that fails the test if anything asks it for a request."""

    def get(self, *args, **kwargs):
        raise AssertionError("no request may be made for this picture path")


class FakeContent:
    def __init__(self, chunks):
        self.chunks = chunks

    async def iter_chunked(self, size):
        for chunk in self.chunks:
            yield chunk


class FakeResponse:
    def __init__(self, status=200, content_type="image/png", chunks=(b"abc",), length=None):
        self.status = status
        self.headers = {"Content-Type": content_type} if content_type else {}
        self.content = FakeContent(list(chunks))
        self.content_length = length

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.urls = []

    def get(self, url, **kwargs):
        self.urls.append((url, kwargs))
        return self.response


def run(coro):
    return asyncio.run(coro)


class PicturePathTests(unittest.TestCase):
    def test_only_home_assistant_picture_paths_are_allowed(self):
        self.assertTrue(picture_path_allowed("/api/image_proxy/image.qr?token=x"))
        self.assertTrue(picture_path_allowed("/api/camera_proxy/camera.door?token=x"))
        for bad in ("http://evil.example/x.png", "https://evil.example/x.png", "//evil.example/x.png",
                    "/local/x.png", "/api/states", "/api/image_proxy/../../x", "/api/image_proxy/./x", "/api/image_proxy/%2e%2e/x",
                    "/api/image_proxy/x/..", "\\\\evil", "", None):
            self.assertFalse(picture_path_allowed(bad), bad)

    def test_absolute_url_is_refused_without_any_request(self):
        sup = Supervisor("http://supervisor", "secret", NoNetwork())
        with self.assertRaises(ApiError) as ctx:
            run(sup.picture("http://evil.example/steal"))
        self.assertEqual(ctx.exception.status, 403)


class PictureFetchTests(unittest.TestCase):
    def test_picture_is_fetched_from_the_supervisor_without_redirects(self):
        session = FakeSession(FakeResponse())
        sup = Supervisor("http://supervisor", "secret", session)
        data, ctype = run(sup.picture("/api/image_proxy/image.qr?token=x"))
        self.assertEqual((data, ctype), (b"abc", "image/png"))
        url, kwargs = session.urls[0]
        self.assertEqual(url, "http://supervisor/core/api/image_proxy/image.qr?token=x")
        self.assertIs(kwargs["allow_redirects"], False)

    def test_svg_and_other_types_are_refused(self):
        sup = Supervisor("http://supervisor", "secret", FakeSession(FakeResponse(content_type="image/svg+xml")))
        with self.assertRaises(ApiError) as ctx:
            run(sup.picture("/api/image_proxy/image.qr"))
        self.assertEqual(ctx.exception.status, 415)

    def test_too_large_picture_is_refused(self):
        big = [b"x" * 65536] * (MAX_PICTURE_BYTES // 65536 + 2)
        sup = Supervisor("http://supervisor", "secret", FakeSession(FakeResponse(chunks=big)))
        with self.assertRaises(ApiError) as ctx:
            run(sup.picture("/api/image_proxy/image.qr"))
        self.assertEqual(ctx.exception.status, 413)

    def test_declared_length_too_large_is_refused_before_reading(self):
        sup = Supervisor("http://supervisor", "secret",
                         FakeSession(FakeResponse(length=MAX_PICTURE_BYTES + 1)))
        with self.assertRaises(ApiError) as ctx:
            run(sup.picture("/api/image_proxy/image.qr"))
        self.assertEqual(ctx.exception.status, 413)


if __name__ == "__main__":
    unittest.main()
