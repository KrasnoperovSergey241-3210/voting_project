from django.utils import timezone
from rest_framework import serializers

from .models import Candidate, JuryMember, Nomination, Vote


class NominationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Nomination
        fields = "__all__"
        read_only_fields = ("created_at", "updated_at", "created_by")

    def validate_title(self, value):
        if Nomination.objects.filter(title=value).exists():
            raise serializers.ValidationError(
                "Номинация с таким названием уже существует"
            )
        if len(value) < 3:
            raise serializers.ValidationError(
                "Название номинации должно содержать минимум 3 символа"
            )
        return value

    def validate(self, attrs):
        if self.instance:
            created_at = self.instance.created_at
            updated_at = attrs.get("updated_at", timezone.now())
            if created_at and updated_at and created_at >= updated_at:
                raise serializers.ValidationError(
                    "Дата обновления должна быть позже даты создания"
                )
        return attrs


class CandidateSerializer(serializers.ModelSerializer):
    nomination = NominationSerializer(read_only=True)
    nomination_id = serializers.PrimaryKeyRelatedField(
        source="nomination",
        queryset=Nomination.objects.all(),
        write_only=True,
        required=False,
    )
    photo_url = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()
    vote_count = serializers.IntegerField(read_only=True)
    favorites_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Candidate
        fields = (
            "id",
            "nomination",
            "nomination_id",
            "name",
            "photo",
            "photo_url",
            "slug",
            "created_at",
            "updated_at",
            "created_by",
            "last_modified_by",
            "is_favorite",
            "vote_count",
            "favorites_count",
        )
        read_only_fields = (
            "created_at",
            "updated_at",
            "created_by",
            "last_modified_by",
            "slug",
        )

    def get_photo_url(self, obj):
        if obj.photo:
            return obj.photo.url
        return None

    def get_is_favorite(self, obj):
        favorites = self.context.get("favorites", [])
        return obj.id in favorites

    def validate_name(self, value):
        if len(value) < 2:
            raise serializers.ValidationError(
                "Имя кандидата должно содержать минимум 2 символа"
            )
        return value


class VoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vote
        fields = ("id", "candidate", "created_at")
        read_only_fields = ("created_at",)

    def validate(self, attrs):
        user = self.context["request"].user
        candidate = attrs["candidate"]

        if not candidate.nomination.is_active:
            raise serializers.ValidationError("Голосование в этой номинации закрыто")

        if Vote.objects.filter(
            user=user, candidate__nomination=candidate.nomination
        ).exists():
            raise serializers.ValidationError("Вы уже голосовали в этой номинации")

        vote = Vote(user=user, candidate=candidate)
        vote.clean()

        return attrs


class JuryMemberSerializer(serializers.ModelSerializer):
    nominations = serializers.PrimaryKeyRelatedField(
        queryset=Nomination.objects.all(), many=True
    )

    class Meta:
        model = JuryMember
        fields = ("id", "name", "nominations")
