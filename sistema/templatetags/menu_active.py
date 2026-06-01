from django import template

register = template.Library()

@register.simple_tag(takes_context=True)
def is_active(context, url_name):
    request = context.get('request')
    if not request:
        return ''
    try:
        current_url_name = request.resolver_match.url_name
        if current_url_name == url_name:
            return 'active'
    except:
        pass
    return ''