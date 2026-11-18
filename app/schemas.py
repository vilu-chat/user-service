from marshmallow import Schema, fields, pre_load, validate


class UserSchema(Schema):
    # Output: public profile
    id = fields.UUID(dump_only=True)
    username = fields.String(allow_none=True, dump_only=True)
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


class UserSearchArgsSchema(Schema):
    q = fields.String(required=True, validate=validate.Length(min=3, max=64))
    limit = fields.Integer(load_default=20, validate=validate.Range(min=1, max=20))

    @pre_load
    def normalise_q(self, data, **kwargs):
        # Trim and lowercase first, so "  AB " fails min=3 and padding does not count towards max=64.
        if hasattr(data, "get") and isinstance(data.get("q"), str):
            data = {key: data[key] for key in data}
            data["q"] = data["q"].strip().lower()
        return data


class RelationListArgsSchema(Schema):
    kind = fields.String(load_default="contact", validate=validate.OneOf(["contact", "pending"]))
    direction = fields.String(load_default="incoming", validate=validate.OneOf(["incoming", "outgoing"]))
    limit = fields.Integer(load_default=50, validate=validate.Range(min=1, max=100))
    cursor = fields.String()


class RelationSchema(Schema):
    other_user_id = fields.UUID(dump_only=True)
    kind = fields.String(dump_only=True)  # contact or pending
    # incoming/outgoing for pending, null for contact
    direction = fields.String(allow_none=True, dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    user = fields.Nested(UserSchema, dump_only=True)  # the other user's public profile


class RelationPageSchema(Schema):
    items = fields.List(fields.Nested(RelationSchema), dump_only=True)
    next_cursor = fields.String(allow_none=True, dump_only=True)


# Events: the payloads stored in outbox_events
class UserUpdatedDataSchema(Schema):
    user_id = fields.UUID(required=True)
    display_name = fields.String(required=True)


class UserDeletedDataSchema(Schema):
    user_id = fields.UUID(required=True)
