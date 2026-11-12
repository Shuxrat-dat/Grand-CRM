from django import forms


class DynamicSearchSelect(forms.Select):
    """
    A lightweight, performant Select widget designed for dynamic AJAX search.
    
    Instead of serializing thousands of <option> elements into HTML (which causes
    lag with large datasets), it only outputs the blank choice and the currently
    selected value (if any). The frontend component dynamically queries the server
    after typing 3+ letters and injects results automatically.
    """
    def __init__(self, *args, search_url=None, placeholder="Qidirish uchun kamida 3 ta harf kiriting...", model=None, **kwargs):
        self.search_url = search_url
        self.placeholder_text = placeholder
        self.model = model
        super().__init__(*args, **kwargs)

    def build_attrs(self, base_attrs, extra_attrs=None):
        attrs = super().build_attrs(base_attrs, extra_attrs)
        classes = attrs.get('class', '')
        if 'dynamic-search-select' not in classes:
            attrs['class'] = (classes + ' dynamic-search-select').strip()
        if self.search_url:
            attrs['data-search-url'] = self.search_url
        attrs['data-placeholder'] = self.placeholder_text
        attrs['data-min-chars'] = '3'
        return attrs

    def optgroups(self, name, value, attrs=None):
        selected_vals = [str(v) for v in (value if isinstance(value, (list, tuple)) else [value]) if v is not None and v != '']
        default_option = self.create_option(name, '', '---------', not selected_vals, 0)
        options = [default_option]

        if selected_vals:
            pk = selected_vals[0]
            label = None
            if self.model:
                try:
                    obj = self.model.objects.get(pk=pk)
                    label = str(obj)
                except (self.model.DoesNotExist, ValueError):
                    pass

            if not label:
                for choice_val, choice_label in self.choices:
                    if str(choice_val) == str(pk):
                        label = str(choice_label)
                        break

            if not label:
                label = f"ID #{pk}"

            options.append(self.create_option(name, pk, label, True, 1))

        return [('', options, 0)]
