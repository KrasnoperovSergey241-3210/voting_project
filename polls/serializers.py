from rest_framework import serializers

from .models import Candidate, JuryMember, Nomination, Vote


class NominationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Nomination
        fields = '__all__'


class CandidateSerializer(serializers.ModelSerializer):
    nomination = NominationSerializer(read_only=True)
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Candidate
        fields = '__all__'

    def get_photo_url(self, obj):
        if obj.photo:
            return obj.photo.url
        return None


class VoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vote
        fields = ('id', 'candidate', 'created_at')
        read_only_fields = ('created_at',)

    def validate(self, attrs):
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


class JuryMemberSerializer(serializers.ModelSerializer):
    nominations = serializers.PrimaryKeyRelatedField(
        queryset=Nomination.objects.all(),
        many=True
    )

    class Meta:
        model = JuryMember
        fields = ('id', 'name', 'nominations')