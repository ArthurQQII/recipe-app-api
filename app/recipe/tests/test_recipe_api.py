"""
Tests for recipe API
"""

import tempfile
import os

from PIL import Image

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from decimal import Decimal

from rest_framework import status  # HTTP status codes
from rest_framework.test import APIClient  # test client

from core.models import Recipe, Tag, Ingredient

from recipe.serializers import RecipeSerializer, RecipeDetailSerializer


RECIPES_URL = reverse("recipe:recipe-list")


def detail_url(recipe_id):
    """Return recipe detail URL"""
    return reverse("recipe:recipe-detail", args=[recipe_id])


def image_upload_url(recipe_id):
    """Return URL for recipe image upload"""
    return reverse("recipe:recipe-upload-image", args=[recipe_id])


def create_recipe(user, **params):
    """Create and return a sample recipe"""
    defaults = {
        "title": "Sample recipe",
        "time_minutes": 10,
        "price": Decimal("5.25"),
        "description": "Sample description",
        "link": "https://sample.com/sample-recipe",
    }
    defaults.update(params)

    return Recipe.objects.create(user=user, **defaults)


def create_user(**params):
    """Create and return a sample user"""
    return get_user_model().objects.create_user(**params)


class PublicRecipeApiTests(TestCase):
    """Test unauthenticated recipe API access"""

    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        """Test that authentication is required"""
        url = RECIPES_URL
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateRecipeApiTests(TestCase):
    """Test authenticated recipe API access"""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user(email="email1@example.com", password="test123")
        self.client.force_authenticate(self.user)

    def test_retrieve_recipes(self):
        """Test retrieving a list of recipes"""
        create_recipe(user=self.user)
        create_recipe(user=self.user)

        url = RECIPES_URL
        response = self.client.get(url)

        recipes = Recipe.objects.all().order_by("-id")
        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, serializer.data)

    def test_recipes_limited_to_user(self):
        """Test retrieving recipes for user"""
        user2 = create_user(email="email2@example.com", password="test123")
        create_recipe(user=user2)
        create_recipe(user=self.user)

        url = RECIPES_URL
        response = self.client.get(url)

        recipes = Recipe.objects.filter(user=self.user)
        serializer = RecipeSerializer(recipes, many=True)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data, serializer.data)

    def test_view_recipe_detail(self):
        """Test viewing a recipe detail"""
        recipe = create_recipe(user=self.user)

        url = detail_url(recipe.id)
        response = self.client.get(url)

        serializer = RecipeDetailSerializer(recipe)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, serializer.data)

    def test_create_recipe(self):
        """Test creating a recipe"""
        payload = {
            "title": "Sample recipe",
            "time_minutes": 10,
            "price": Decimal("5.25"),
        }

        url = RECIPES_URL
        response = self.client.post(url, payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        recipe = Recipe.objects.get(id=response.data["id"])

        for key in payload.keys():
            self.assertEqual(payload[key], getattr(recipe, key))
        self.assertEqual(recipe.user, self.user)

    def test_partial_update(self):
        original_link = "https://sample.com/sample-recipe"
        recipe = create_recipe(
            user=self.user, title="Sample recipe", link=original_link
        )

        payload = {"title": "New title"}
        url = detail_url(recipe.id)
        self.client.patch(url, payload)

        recipe.refresh_from_db()
        self.assertEqual(recipe.title, payload["title"])
        self.assertEqual(recipe.link, original_link)
        self.assertEqual(recipe.user, self.user)

    def test_full_update(self):
        recipe = create_recipe(
            user=self.user,
            title="Sample recipe",
            link="https://sample.com/sample-recipe",
            description="Sample description",
        )

        payload = {
            "title": "New title",
            "time_minutes": 10,
            "price": Decimal("5.25"),
            "description": "New description",
            "link": "https://sample.com/new-recipe",
        }

        url = detail_url(recipe.id)
        self.client.put(url, payload)

        recipe.refresh_from_db()
        for key in payload.keys():
            self.assertEqual(payload[key], getattr(recipe, key))
        self.assertEqual(recipe.user, self.user)

    def test_update_user_return_error(self):
        new_user = create_user(email="eee@email.com", password="test123")
        recipe = create_recipe(user=self.user)

        payload = {"user": new_user}

        url = detail_url(recipe.id)
        self.client.patch(url, payload)

        recipe.refresh_from_db()

        self.assertEqual(self.user, recipe.user)

    def test_delete_recipe(self):
        """Test deleting a recipe"""
        recipe = create_recipe(user=self.user)

        url = detail_url(recipe.id)
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        exists = Recipe.objects.filter(id=recipe.id).exists()
        self.assertFalse(exists)

    def test_delete_other_users_recipe_error(self):
        """Test that user can't delete other user's recipe"""
        user2 = create_user(email="userse@email.com", password="test123")
        recipe = create_recipe(user=user2)

        url = detail_url(recipe.id)
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Recipe.objects.filter(id=recipe.id).exists())

    def test_create_recipe_with_new_tags(self):
        """Test creating a recipe with new tags"""
        Tag.objects.create(user=self.user, name="Tag1")
        Tag.objects.create(user=self.user, name="Tag2")

        payload = {
            "title": "Sample recipe",
            "time_minutes": 10,
            "price": Decimal("5.25"),
            "tags": [{"name": "Tag1"}, {"name": "Tag2"}],
        }

        url = RECIPES_URL
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        recipe = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipe.count(), 1)
        tags = recipe[0].tags.all()

        self.assertEqual(tags.count(), 2)
        for tag in payload["tags"]:
            exists = tags.filter(name=tag["name"]).exists()
            self.assertTrue(exists)

    def test_create_recipe_with_existing_tags(self):
        tag_indian = Tag.objects.create(user=self.user, name="Indian")

        payload = {
            "title": "Pongal",
            "time_minutes": 60,
            "price": Decimal("3.6"),
            "tags": [{"name": "Indian"}, {"name": "Breakfast"}],
        }

        res = self.client.post(RECIPES_URL, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        recipe = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipe.count(), 1)
        tags = recipe[0].tags.all()

        self.assertEqual(tags.count(), 2)
        self.assertIn(tag_indian, tags)

        for tag in payload["tags"]:
            exists = tags.filter(name=tag["name"], user=self.user).exists()
            self.assertTrue(exists)

    def test_create_tage_on_update(self):
        recipe = create_recipe(user=self.user)

        payload = {"tags": [{"name": "Indian"}]}

        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        new_tag = Tag.objects.get(user=self.user, name="Indian")
        self.assertIn(new_tag, recipe.tags.all())

    def test_update_recipe_assign_tag(self):
        tag_breakfast = Tag.objects.create(user=self.user, name="Breakfast")
        recipe = create_recipe(user=self.user)
        recipe.tags.add(tag_breakfast)

        tag_lunch = Tag.objects.create(user=self.user, name="Lunch")
        payload = {"tags": [{"name": "Lunch"}]}

        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertEqual(recipe.tags.count(), 1)
        self.assertIn(tag_lunch, recipe.tags.all())
        self.assertNotIn(tag_breakfast, recipe.tags.all())

    def test_clear_recipe_tags(self):
        tag = Tag.objects.create(user=self.user, name="Breakfast")
        recipe = create_recipe(user=self.user)
        recipe.tags.add(tag)

        payload = {"tags": []}

        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.tags.count(), 0)

    def test_create_recipe_with_new_ingredients(self):
        payload = {
            "title": "Sample recipe",
            "time_minutes": 10,
            "price": Decimal("5.25"),
            "ingredients": [{"name": "Ingredient1"}, {"name": "Ingredient2"}],
        }

        url = RECIPES_URL
        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        recipe = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipe.count(), 1)
        ingredients = recipe[0].ingredients.all()

        self.assertEqual(ingredients.count(), 2)
        for ingredient in payload["ingredients"]:
            exists = ingredients.filter(name=ingredient["name"]).exists()
            self.assertTrue(exists)

    def test_create_recipe_with_existing_ingredients(self):
        ingredient_rice = Ingredient.objects.create(
            user=self.user,
            name="Rice"
        )

        payload = {
            "title": "Pongal",
            "time_minutes": 60,
            "price": Decimal("3.6"),
            "ingredients": [{"name": "Rice"}, {"name": "Moong Dal"}],
        }

        res = self.client.post(RECIPES_URL, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        recipe = Recipe.objects.filter(user=self.user)
        self.assertEqual(recipe.count(), 1)
        ingredients = recipe[0].ingredients.all()

        self.assertEqual(ingredients.count(), 2)
        self.assertIn(ingredient_rice, ingredients)

        for ingredient in payload["ingredients"]:
            exists = ingredients.filter(
                name=ingredient["name"], user=self.user
            ).exists()
            self.assertTrue(exists)

    def test_create_ingredient_on_update(self):
        recipe = create_recipe(user=self.user)

        payload = {"ingredients": [{"name": "Rice"}]}

        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        new_ingredient = Ingredient.objects.get(user=self.user, name="Rice")
        self.assertIn(new_ingredient, recipe.ingredients.all())

    def test_update_recipe_assign_ingredient(self):
        ingredient_rice = Ingredient.objects.create(
            user=self.user,
            name="Rice"
        )
        recipe = create_recipe(user=self.user)
        recipe.ingredients.add(ingredient_rice)

        ingredient_moong_dal = Ingredient.objects.create(
            user=self.user, name="Moong Dal"
        )
        payload = {"ingredients": [{"name": "Moong Dal"}]}

        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.assertEqual(recipe.ingredients.count(), 1)
        self.assertIn(ingredient_moong_dal, recipe.ingredients.all())
        self.assertNotIn(ingredient_rice, recipe.ingredients.all())

    def test_clear_recipe_ingredients(self):
        ingredient_rice = Ingredient.objects.create(
            user=self.user,
            name="Rice"
        )
        recipe = create_recipe(user=self.user)
        recipe.ingredients.add(ingredient_rice)

        payload = {"ingredients": []}

        url = detail_url(recipe.id)
        res = self.client.patch(url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(recipe.ingredients.count(), 0)


class RecipeImageUploadTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user(
            email="userser@example.com",
            password="test123"
        )
        self.client.force_authenticate(self.user)
        self.recipe = create_recipe(user=self.user)

    def tearDown(self):
        self.recipe.image.delete()

    def test_upload_image_to_recipe(self):
        url = image_upload_url(self.recipe.id)
        with tempfile.NamedTemporaryFile(suffix=".jpg") as temp_file:
            image = Image.new("RGB", (10, 10))
            image.save(temp_file, format="JPEG")
            temp_file.seek(0)
            response = self.client.post(
                url, {"image": temp_file},
                format="multipart"
            )

        self.recipe.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("image", response.data)
        self.assertTrue(os.path.exists(self.recipe.image.path))

    def test_upload_image_bad_request(self):
        url = image_upload_url(self.recipe.id)
        response = self.client.post(
            url, {"image": "notimage"},
            format="multipart"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
