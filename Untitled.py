import appex
import clipboard

def main():
	if not appex.is_running_extension():
		print('Running in Pythonista app, using test data...\n')
		text = 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
	else:
		text = appex.get_text()
	if text:
		# TODO: Your own logic here...
		print('Input text: %s' % text)
		out = text.upper()
		print('\nConverted to all-caps: %s' % out)
		clipboard.set(out)
		print('(Copied to clipboard)')
	else:
		print('No input text found.')

if __name__ == '__main__':
	main()