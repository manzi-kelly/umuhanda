import { test } from 'node:test';
import { createRequire } from 'node:module';
const load = createRequire(import.meta.url);
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';

// Compile project TypeScript with the installed compiler, without another test dependency.
load.extensions['.ts'] = (module, filename) => {
  const source = fs.readFileSync(filename, 'utf8');
  module._compile(ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
    fileName: filename,
  }).outputText, filename);
};
const { normalizeRwandaPhone } = load('../src/lib/phone.ts');
const { validateStudent } = load('../src/features/onboarding/validation.ts');
const { initiatePayment } = load('../src/features/payment/api.ts');
const { redeemPromo } = load('../src/features/promo/api.ts');

test('normalizes supported local and international formats across mobile ranges', () => {
  for (const prefix of ['72', '73', '77', '78', '79']) {
    for (const value of [`0${prefix}1234567`, `+250${prefix}1234567`, `250${prefix}1234567`, `${prefix}1234567`]) {
      assert.equal(normalizeRwandaPhone(value), `+250${prefix}1234567`);
    }
  }
  assert.equal(normalizeRwandaPhone(' +250 (78) 123-4567 '), '+250781234567');
});
test('rejects reserved ranges, landlines, foreign, malformed and wrong length numbers', () => {
  for (const value of ['', ' ', '0701234567', '0711234567', '0741234567', '0751234567', '0761234567', '0251234567', '+254781234567', '078123456', '07812345678', '0781234567 ext 1', '++250781234567', '+2500781234567', '0781234.567']) {
    assert.equal(normalizeRwandaPhone(value), null, value);
  }
});
test('required fields, names and invalid phone prevent progression', () => {
  for (const fullName of ['', '   ', '123', '<script>', 'A'.repeat(121)]) {
    const result = validateStudent({ fullName, phoneNumber: '0781234567' });
    assert.equal(result.student, null);
    assert.ok(result.errors.fullName);
  }
  const result = validateStudent({ fullName: 'Test Student', phoneNumber: '123' });
  assert.equal(result.student, null);
  assert.ok(result.errors.phoneNumber);
  assert.equal(Object.keys(validateStudent({ fullName: '', phoneNumber: '' }).errors).length, 2);
});
test('normalizes names while preserving Unicode and name punctuation', () => {
  for (const fullName of ['Élodie Uwase', "Jean-Luc O’Neil", '李 明']) {
    assert.equal(validateStudent({ fullName, phoneNumber: '0781234567' }).student.fullName, fullName);
  }
  assert.deepEqual(validateStudent({ fullName: '  Test   Student  ', phoneNumber: '0781234567' }).student,
    { fullName: 'Test Student', phoneNumber: '+250781234567' });
});
test('payment and arbitrary promo cannot approve or grant access and make no network request', async () => {
  const previousFetch = global.fetch;
  global.fetch = () => { throw new Error('Network request forbidden in Phase 02'); };
  try {
    const student = { fullName: 'Test Student', phoneNumber: '+250781234567' };
    for (const provider of ['MTN', 'AIRTEL']) {
      assert.deepEqual(await initiatePayment({ student, provider, phoneNumber: student.phoneNumber }),
        { status: 'VERIFICATION_UNAVAILABLE', accessGranted: false });
    }
    assert.deepEqual(await redeemPromo({ student, code: 'ANY-CODE' }),
      { status: 'VERIFICATION_UNAVAILABLE', accessGranted: false });
  } finally { global.fetch = previousFetch; }
});

