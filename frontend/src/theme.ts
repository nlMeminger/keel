import {
  createTheme,
  NativeSelect,
  NumberInput,
  PasswordInput,
  Select,
  Textarea,
  TextInput,
} from '@mantine/core'

const systemFontStack = "system-ui, 'Segoe UI', Roboto, sans-serif"

// `required` otherwise renders a visible "*" inside the <label>, which turns its
// accessible text into "Email *" and breaks exact getByLabelText('Email') queries.
// The native `required` attribute still applies; this only drops the asterisk.
const noAsterisk = { defaultProps: { withAsterisk: false } }

// Nautical-tinted neutral: teal accent, Mantine's default gray for everything else
// so financial data stays legible.
export const theme = createTheme({
  primaryColor: 'teal',
  defaultRadius: 'md',
  fontFamily: systemFontStack,
  headings: { fontFamily: systemFontStack },
  components: {
    TextInput: TextInput.extend(noAsterisk),
    PasswordInput: PasswordInput.extend(noAsterisk),
    NumberInput: NumberInput.extend(noAsterisk),
    Textarea: Textarea.extend(noAsterisk),
    NativeSelect: NativeSelect.extend(noAsterisk),
    Select: Select.extend(noAsterisk),
  },
})
