"""
Tests for th tags API
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import TestCase

from rest_framework import status  # HTTP status codes
from rest_framework.test import APIClient

from core.models import Tag

from recipe.serializers import TagSerializer

# URL for the tags list
TAGS_URL = reverse("recipe:tag-list")


def detail_url(tag_id):
    """Return the URL for the tag detail"""
    return reverse("recipe:tag-detail", args=[tag_id])


def create_user(email="user@example.com", password="password"):
    """Helper function to create a user"""
    return get_user_model().objects.create_user(email, password)


class PublicTagsApiTests(TestCase):
    """Test the publicly available tags API"""

    def setUp(self):
        self.client = APIClient()

    def test_login_required(self):
        """Test that login is required for retrieving tags"""

        # Attempt to retrieve tags without logging in
        res = self.client.get(TAGS_URL)

        # Assert that the request failed
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateTagsApiTests(TestCase):
    def setUp(self):
        self.user = create_user()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_retrieve_tags(self):
        """Test retrieving tags"""

        # Create some tags
        Tag.objects.create(user=self.user, name="Vegan")
        Tag.objects.create(user=self.user, name="Dessert")

        # Retrieve tags
        res = self.client.get(TAGS_URL)

        # Get all tags for the user
        tags = Tag.objects.all().order_by("-name")

        # Serialize the tags
        serializer = TagSerializer(tags, many=True)

        # Assert that the request was successful
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Assert that the tags are the same
        self.assertEqual(res.data, serializer.data)

    def test_tags_limited_to_user(self):
        """Test that tags returned are for the authenticated user"""

        # Create a new user
        user2 = create_user(email="use@emaple.com", password="password")

        # Create some tags for the new user
        Tag.objects.create(user=user2, name="Fruity")
        tag = Tag.objects.create(user=self.user, name="Comfort Food")

        # Retrieve tags
        res = self.client.get(TAGS_URL)

        # Assert that the request was successful
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Assert that only the tag for the authenticated user is returned
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["name"], tag.name)

    def test_update_tag(self):
        tag = Tag.objects.create(user=self.user, name="Test Tag")

        payload = {"name": "New Tag Name"}
        url = detail_url(tag.id)
        res = self.client.patch(url, payload)

        tag.refresh_from_db()

        self.assertEqual(tag.name, payload["name"])
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_delete_tag(self):
        tag = Tag.objects.create(user=self.user, name="Test Tag")

        url = detail_url(tag.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

        self.assertEqual(Tag.objects.count(), 0)
