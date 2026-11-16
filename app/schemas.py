from marshmallow import Schema, fields, pre_load, validate


class UserSchema(Schema):
    # Output: public profile
    id = fields.UUID(dump_only=True)
    display_name = fields.String(dump_only=True)
    bio = fields.String(allow_none=True, dump_only=True)
    status_text = fields.String(allow_none=True, dump_only=True)
    # Built by the service once avatars exist; always present, null until then.
    avatar_url = fields.String(allow_none=True, dump_only=True, dump_default=None)


class UserMeSchema(UserSchema):
    locale = fields.String(allow_none=True, dump_only=True)
    timezone = fields.String(allow_none=True, dump_only=True)
    created_at = fields.DateTime(dump_only=True)


class UserUpdateSchema(Schema):
    # PATCH: no load_default, so only the fields the client sent are applied
    display_name = fields.String(validate=validate.Length(min=1, max=64))
    bio = fields.String(allow_none=True, validate=validate.Length(max=500))
    status_text = fields.String(allow_none=True, validate=validate.Length(max=140))
    locale = fields.String(allow_none=True, validate=validate.Length(max=10))
    timezone = fields.String(allow_none=True, validate=validate.Length(max=64))

    @pre_load
    def trim_display_name(self, data, **kwargs):
        # Trim first, so a blank name fails min=1 and padding does not count towards max=64.
        if isinstance(data, dict) and isinstance(data.get("display_name"), str):
            data = {**data, "display_name": data["display_name"].strip()}
        return data


class UserLookupSchema(Schema):
    ids = fields.List(
        fields.UUID(), required=True, validate=validate.Length(min=1, max=100)
    )


# Events: the payloads stored in outbox_events
class UserUpdatedDataSchema(Schema):
    user_id = fields.UUID(required=True)
    display_name = fields.String(required=True)


class UserDeletedDataSchema(Schema):
    user_id = fields.UUID(required=True)
