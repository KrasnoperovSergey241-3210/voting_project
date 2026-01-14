from rest_framework import serializers

from .models import Candidate, Nomination, Vote


class NominationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Nomination
        fields = '__all__'


class CandidateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Candidate
        fields = '__all__'


class VoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vote
        fields = ('id', 'candidate', 'created_at')

    def validate(self, attrs):
        """Кастомная логика валидации"""
        user = self.context['request'].user
        candidate = attrs['candidate']
        nomination = candidate.nomination

        if Vote.objects.filter(
            user=user,
            candidate__nomination=nomination
        ).exists():
            raise serializers.ValidationError(
                'Вы уже голосовали в этой номинации'
            )

        return attrs
    def validate_title(self, value):
        if len(value) < 3:
            raise serializers.ValidationError("Название номинации слишком короткое")
        return value

