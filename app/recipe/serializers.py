"""
Serializers for Recipe app
"""

from rest_framework import serializers

from core.models import Recipe, Tag


class TagSerializer(serializers.ModelSerializer):
    """Serializer for Tag objects"""

    class Meta:
        model = Tag
        fields = ["id", "name"]
        read_only_fields = ["id"]


class RecipeSerializer(serializers.ModelSerializer):
    """Serializer for Recipe objects"""

    tags = TagSerializer(many=True, required=False)

    class Meta:
        model = Recipe
        fields = ["id", "title", "time_minutes", "price", "link", "tags"]
        read_only_fields = ["id"]

    def _get_or_create_tags(self, instance, tags_data):
        """Get or create tags"""
        auth_user = self.context["request"].user
        for tag_data in tags_data:
            tag, created = Tag.objects.get_or_create(
                user=auth_user,
                **tag_data
            )
            instance.tags.add(tag)

    def create(self, validated_data):
        """Create a new Recipe"""
        tags_data = validated_data.pop("tags", [])
        recipe = Recipe.objects.create(**validated_data)
        self._get_or_create_tags(recipe, tags_data)

        return recipe

    def update(self, instance, validated_data):
        """Update a Recipe"""
        tags_data = validated_data.pop("tags", [])

        if tags_data is not None:
            instance.tags.clear()
            self._get_or_create_tags(instance, tags_data)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


class RecipeDetailSerializer(RecipeSerializer):
    """Serializer for Recipe detail objects"""

    description = serializers.CharField(required=False)

    class Meta(RecipeSerializer.Meta):
        fields = RecipeSerializer.Meta.fields + ["description"]
