from __future__ import annotations

from stokenizer import stokenizer


class XMLNode:
	def __init__(self, tagname, attributes, text, children, namespaces):
		self.tagname = tagname
		self.attributes = attributes
		self.text = text
		self.children = children
		self.namespaces = namespaces

	def local_name(self):
		_, _, postfix = self.tagname.rpartition(':')
		return postfix


class XMLFile:
	doctype: XMLNode
	root: XMLNode

	def __init__(self, root: XMLNode, doctype: XMLNode = None):
		self.root = root
		self.doctype = doctype


def parse_xml_declaration(tokens: list[stokenizer.Token], i: int) -> tuple[XMLNode, int]:
	tagname = tokens[i].text
	i += 1

	attributes = {}
	while True:
		token, i = stokenizer.skip_whitespaces(tokens, i)
		if token.kind == stokenizer.TokenKind.OPERATOR and tokens[i].text == '?':
			assert tokens[i+1].kind == stokenizer.TokenKind.OPERATOR and tokens[i+1].text == '>'
			i += 2
			break
		elif token.kind == stokenizer.TokenKind.IDENTIFIER:
			attribute_key = token.text
			if tokens[i+1].kind == stokenizer.TokenKind.OPERATOR and tokens[i+1].text == ':':
				attribute_key += ':' + tokens[i+2].text
				i += 2
			
			token, i = stokenizer.skip_whitespaces(tokens, i+1)
			assert token.kind == stokenizer.TokenKind.OPERATOR
			token, i = stokenizer.advance(tokens, i)
			assert token.kind == stokenizer.TokenKind.QUOTED
			attribute_value = token.unquoted()
			attributes[attribute_key] = attribute_value
			i += 1
	return XMLNode(tagname, attributes, None, None, None), i


def parse_tag_attributes_and_namespaces(tokens: list[stokenizer.Token], i: int) -> tuple[dict[str, str], dict[str, str], int]:
	attributes = {}
	namespaces = {}
	while True:
		token, i = stokenizer.skip_whitespaces(tokens, i)
		if token.kind == stokenizer.TokenKind.OPERATOR and token.text == '>':
			i += 1
			break
		elif token.kind == stokenizer.TokenKind.OPERATOR and token.text == '/':
			assert tokens[i+1].kind == stokenizer.TokenKind.OPERATOR and tokens[i+1].text == '>'
			i += 2
			break
		elif token.kind == stokenizer.TokenKind.IDENTIFIER:
			attribute_key = token.text
			prefix = ''
			postfix = attribute_key
			if tokens[i+1].kind == stokenizer.TokenKind.OPERATOR and tokens[i+1].text == ':':
				prefix = attribute_key
				postfix = tokens[i+2].text
				attribute_key += ':' + tokens[i+2].text
				i += 2
			
			token, i = stokenizer.skip_whitespaces(tokens, i+1)
			assert token.kind == stokenizer.TokenKind.OPERATOR
			token, i = stokenizer.advance(tokens, i)
			assert token.kind == stokenizer.TokenKind.QUOTED
			attribute_value = token.unquoted()
			if prefix == 'xmlns':
				namespaces[postfix] = attribute_value
			elif postfix == 'xmlns':
				namespaces[''] = attribute_value
			else:
				attributes[attribute_key] = attribute_value
			i += 1
	return attributes, namespaces, i


def parse_node(tokens: list[stokenizer.Token], i=0) -> XMLNode:
	if tokens[i].kind == stokenizer.TokenKind.OPERATOR and tokens[i].text == '<':
		token, i = stokenizer.advance(tokens, i)
		tagname = token.text
		i += 1
		if tokens[i].kind == stokenizer.TokenKind.OPERATOR and tokens[i].text == ':':
			tagname += ':' + tokens[i+1].text
			i += 2
		
		attributes, namespaces, i = parse_tag_attributes_and_namespaces(tokens, i)

		if tokens[i-2].kind == stokenizer.TokenKind.OPERATOR and tokens[i-2].text == '/':
			return XMLNode(tagname, attributes, '', [], namespaces), i

		text = ''
		while tokens[i].kind != stokenizer.TokenKind.OPERATOR or tokens[i].text != '<':
			text += tokens[i].text
			i += 1
		children = []
		at_opening_bracket = i
		token, i = stokenizer.advance(tokens, i)
		while tokens[i].kind == stokenizer.TokenKind.IDENTIFIER:
			node, i = parse_node(tokens, at_opening_bracket)
			children.append(node)
			post_text = ''
			while tokens[i].kind != stokenizer.TokenKind.OPERATOR or tokens[i].text != '<':
				post_text += tokens[i].text
				i += 1
			text += post_text.strip()
			assert tokens[i].text == '<'
			at_opening_bracket = i
			token, i = stokenizer.advance(tokens, i)

		token, i = stokenizer.skip_whitespaces(tokens, i)
		if token.kind == stokenizer.TokenKind.OPERATOR and token.text == '/':
			token, i = stokenizer.advance(tokens, i)
			closing_tagname = token.text
			if tokens[i+1].kind == stokenizer.TokenKind.OPERATOR and tokens[i+1].text == ':':
				closing_tagname += ':' + tokens[i+2].text
				i += 2
			assert closing_tagname == tagname
			assert tokens[i+1].text == '>'
			return XMLNode(tagname, attributes, text.strip(), children, namespaces), i + 2


def parse(xml: str) -> XMLFile:
	tokens = stokenizer.tokenize(xml)
	token, i = stokenizer.skip_whitespaces(tokens, 0)
	assert token.kind == stokenizer.TokenKind.OPERATOR and token.text == '<'
	xml_declaration = None
	if tokens[i+1].kind == stokenizer.TokenKind.OPERATOR and tokens[i+1].text == '?':
		_, i = stokenizer.advance(tokens, i+1)
		xml_declaration, i = parse_xml_declaration(tokens, i)
		_, i = stokenizer.skip_whitespaces(tokens, i)

	nodes, _ = parse_node(tokens, i)
	return XMLFile(nodes, xml_declaration)


def print_xml(out, root, indent=0, /, empty_tag_style: 'short'|'uniform' = 'short'):
	tag_contents = [root.tagname]
	tag_contents.extend(f'xmlns:{key}="{value}"' for key, value in root.namespaces.items())
	tag_contents.extend(f'{key}="{value}"' for key, value in root.attributes.items())
	if len(root.children) > 0:
		out.write(('\t' * indent) + '<' + ' '.join(tag_contents) + '>\n')
		if len(root.text) > 0:
			out.write(('\t' * (indent + 1)) + root.text + '\n')
		for it in root.children:
			print_xml(out, it, indent + 1, empty_tag_style=empty_tag_style)
		out.write(('\t' * indent) + f'</{root.tagname}>\n')
	else:
		if len(root.text) == 0 and empty_tag_style == 'short':
			out.write(('\t' * indent) + '<' + ' '.join(tag_contents) + ' />\n')
		else:
			out.write(('\t' * indent) + '<' + ' '.join(tag_contents) + '>' + root.text + f'</{root.tagname}>\n')


def print_xml_file(out, file: XMLFile, /, empty_tag_style: 'short'|'uniform' = 'short'):
	if file.doctype is not None:
		tag_contents = [file.doctype.tagname]
		tag_contents.extend(f'{key}="{value}"' for key, value in file.doctype.attributes.items())
		out.write('<?' + ' '.join(tag_contents) + '?>\n')
	print_xml(out, file.root, empty_tag_style=empty_tag_style)


def main():
	import sys

	filename = sys.argv[1]
	with open(filename, 'r') as f:
		contents = f.read()
	file = parse(contents)
	print_xml_file(sys.stdout, file)


if __name__ == '__main__':
	main()
