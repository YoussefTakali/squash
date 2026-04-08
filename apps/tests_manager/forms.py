"""Forms for tests manager app."""
from django import forms


class TestSuiteForm(forms.Form):
    """Form for creating/editing a test suite."""
    name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Suite Name',
        })
    )
    robot_directory = forms.CharField(
        max_length=500,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'C:/path/to/robot/tests',
        })
    )
    squash_iteration_id = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': 'Squash Iteration ID (optional)',
        })
    )
    squash_campaign_id = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': 'Squash Campaign ID (optional)',
        })
    )

    def clean_robot_directory(self):
        """Validate that the directory exists."""
        from pathlib import Path
        directory = self.cleaned_data['robot_directory']
        path = Path(directory)

        if not path.exists():
            raise forms.ValidationError(f"Directory does not exist: {directory}")

        if not path.is_dir():
            raise forms.ValidationError(f"Path is not a directory: {directory}")

        return directory


class MappingForm(forms.Form):
    """Form for a single test mapping."""
    robot_test_name = forms.CharField(widget=forms.HiddenInput())
    squash_test_case_id = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-input mapping-input',
            'placeholder': 'Squash ID',
        })
    )
