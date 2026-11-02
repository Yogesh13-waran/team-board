"""
Serializers for TeamBoard API.

================================================================================
INTERVIEW DEEP-DIVE: DRF SERIALIZERS & VALIDATION LIFECYCLE
================================================================================
1. The Role of Serializers in DRF:
   - Bidirectional Translation:
     * Deserialization: JSON payload -> Python primitive types -> Model instance / validated dict.
     * Serialization: Model instance / QuerySet -> Python dict -> JSON response.
   - Security Boundary:
     * Prevents Mass Assignment vulnerabilities by strictly declaring writeable fields.
     * For instance, `role` and `api_key` are protected from client tampering during registration.

2. DRF Validation Sequence:
   - When `serializer.is_valid(raise_exception=True)` is called:
     1. Field-level type coercion & validators (e.g. `CharField(max_length=255)`).
     2. Custom field validation methods: `validate_<field_name>(self, value)`.
     3. Cross-field object-level validation: `validate(self, attrs)`.
     4. Populates `.validated_data` on success, or `.errors` and raises `ValidationError`.

3. Password Handling & Security:
   - Passwords must always have `write_only=True` so they are never returned in responses.
   - Django hashes passwords using PBKDF2 with SHA-256 and high work-factor iterations,
     preventing rainbow table attacks.
================================================================================
"""

from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Company, KBEntry, QueryLog


class RegisterSerializer(serializers.Serializer):
    """
    Validates and deserializes incoming customer registration requests.
    Enforces required fields and ensures unique username validation.
    """
    username = serializers.CharField(
        max_length=150,
        required=True,
        error_messages={
            'blank': 'Username cannot be blank.',
            'required': 'Username is required.'
        }
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        error_messages={
            'blank': 'Password cannot be blank.',
            'required': 'Password is required.'
        }
    )
    company_name = serializers.CharField(
        max_length=255,
        required=True,
        error_messages={
            'blank': 'Company name cannot be blank.',
            'required': 'Company name is required.'
        }
    )
    email = serializers.EmailField(
        required=True,
        error_messages={
            'blank': 'Email cannot be blank.',
            'required': 'Email is required.',
            'invalid': 'Please enter a valid email address.'
        }
    )

    def validate_username(self, value):
        """
        Verify that the username is not already registered.
        Returns HTTP 400 when validation fails.
        """
        cleaned_username = value.strip()
        if not cleaned_username:
            raise serializers.ValidationError("Username cannot be empty or whitespace.")
        if User.objects.filter(username__iexact=cleaned_username).exists():
            raise serializers.ValidationError("A user with that username already exists.")
        return cleaned_username

    def validate_company_name(self, value):
        cleaned_company_name = value.strip()
        if not cleaned_company_name:
            raise serializers.ValidationError("Company name cannot be empty or whitespace.")
        return cleaned_company_name


class LoginSerializer(serializers.Serializer):
    """
    Validates user credentials for JWT token generation.
    """
    username = serializers.CharField(
        required=True,
        error_messages={
            'blank': 'Username cannot be blank.',
            'required': 'Username is required.'
        }
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        error_messages={
            'blank': 'Password cannot be blank.',
            'required': 'Password is required.'
        }
    )


class KBEntrySerializer(serializers.ModelSerializer):
    """
    Serializes Knowledge Base entries for query response output.
    """
    class Meta:
        model = KBEntry
        fields = ['id', 'question', 'answer', 'category']


class KBQueryRequestSerializer(serializers.Serializer):
    """
    Validates search query requests.
    Enforces non-empty, non-blank search terms.
    """
    search = serializers.CharField(
        required=True,
        allow_blank=False,
        error_messages={
            'required': 'Search term is required.',
            'blank': 'Search term cannot be blank.'
        }
    )

    def validate_search(self, value):
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Search term cannot be empty or whitespace.")
        return cleaned


class TopSearchTermSerializer(serializers.Serializer):
    """
    Serializes top search term aggregations for usage dashboard.
    """
    search_term = serializers.CharField()
    count = serializers.IntegerField()


class UsageSummarySerializer(serializers.Serializer):
    """
    Serializes platform-wide usage metrics.
    """
    total_queries = serializers.IntegerField()
    active_companies = serializers.IntegerField()
    top_search_terms = TopSearchTermSerializer(many=True)
