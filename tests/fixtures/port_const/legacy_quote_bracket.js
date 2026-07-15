// Legacy Vue constant — a string element intentionally contains a raw ']'
// character, to prove the extractor's string-skipping does not treat it
// as closing the array early.
export const LABEL_OPTIONS = [
  'note: array like [a, b]',
  'plain',
];
