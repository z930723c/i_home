from wtforms import Form, StringField, IntegerField
from wtforms import validators


class HouseForm(Form):
    title = StringField(
        label="房屋标题",
        validators=[validators.Length(
            min=1,max=66,message="房屋标题必须在1到66个字符之间")
        ])
    price = IntegerField(
        label="房屋单价",
        validators=[validators.NumberRange(min=1)],
        default=1
    )
    pass