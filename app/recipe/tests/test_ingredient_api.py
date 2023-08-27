""""
Test the ingredients API
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import TestCase

from rest_framework import status
from rest_framework.test import APIClient

from core.models import Ingredient

from recipe.serializers import IngredientSerializer


INGREDIENTS_URL = reverse("recipe:ingredient-list")


def detail_url(ingredient_id):
    """Return ingredient detail URL"""
    return reverse("recipe:ingredient-detail", args=[ingredient_id])


def create_user(email="example@email.com", password="test"):
    """Create and return a sample user"""
    return get_user_model().objects.create_user(email, password)


class PublicIngredientsApiTests(TestCase):
    """Test the publicly available ingredients API"""

    def setUp(self):
        self.client = APIClient()

    def test_login_required(self):
        """Test that login is required to access the endpoint"""
        response = self.client.get(INGREDIENTS_URL)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateIngredientsApiTests(TestCase):
    """Test the private ingredients API"""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user()
        self.client.force_authenticate(self.user)

    def test_retrieve_ingredients_list(self):
        """Test retrieving a list of ingredients"""
        Ingredient.objects.create(user=self.user, name="Kale")
        Ingredient.objects.create(user=self.user, name="Salt")

        response = self.client.get(INGREDIENTS_URL)

        ingredients = Ingredient.objects.all().order_by("-name")
        serializer = IngredientSerializer(ingredients, many=True)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, serializer.data)

    def test_ingredients_limited_to_user(self):
        """Test that ingredients for the authenticated user are returned"""
        user2 = create_user(email="user@eeeeeee.com", password="testpass")
        Ingredient.objects.create(user=user2, name="Vinegar")
        ingredient = Ingredient.objects.create(user=self.user, name="Tumeric")

        response = self.client.get(INGREDIENTS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], ingredient.name)

        self.assertEqual(response.data[0]["id"], ingredient.id)

    def test_update_ingredient_successful(self):
        """Test updating an ingredient with patch"""
        ingredient = Ingredient.objects.create(user=self.user, name="Tumeric")
        payload = {"name": "Cabbage"}
        url = detail_url(ingredient.id)
        res = self.client.patch(url, payload)

        ingredient.refresh_from_db()

        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertEqual(ingredient.name, payload["name"])

    def test_delete_infredients(self):
        """Test deleting ingredients"""
        ingredient = Ingredient.objects.create(user=self.user, name="Tumeric")
        url = detail_url(ingredient.id)
        res = self.client.delete(url)

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

        self.assertEqual(Ingredient.objects.count(), 0)
