import { createTheme } from '@mantine/core'

const systemFontStack = "system-ui, 'Segoe UI', Roboto, sans-serif"

// Nautical-tinted neutral: teal accent, Mantine's default gray for everything else
// so financial data stays legible.
export const theme = createTheme({
  primaryColor: 'teal',
  defaultRadius: 'md',
  fontFamily: systemFontStack,
  headings: { fontFamily: systemFontStack },
})
