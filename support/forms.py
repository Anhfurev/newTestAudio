from django import forms

from .models import ApartmentLead


class ApartmentLeadForm(forms.ModelForm):
	class Meta:
		model = ApartmentLead
		fields = [
			"owner_name",
			"owner_phone",
			"title",
			"location",
			"price",
			"bedrooms",
			"area_sqm",
			"description",
		]
		widgets = {
			"description": forms.Textarea(attrs={"rows": 4}),
		}


class ApartmentPublishForm(forms.Form):
	agent_phone = forms.CharField(max_length=40, label="Agent phone")



