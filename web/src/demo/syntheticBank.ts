export type Transaction = { id: string; customerId: string; merchant: string; amountCents: number; currency: string; date: string; status: string };
export type Request = { id: string; customerId: string; name: string; transactionId: string; amountCents: number; currency: string; subject: string; message: string };
export type Dispute = { id: string; requestId: string; transactionId: string; customerId: string; amountCents: number; currency: string };
export const requests: Request[] = [
  { id: 'REQ-1001', customerId: 'CUS-2041', name: 'Alex Morgan', transactionId: 'TXN-81001', amountCents: 12999, currency: 'USD', subject: 'Unrecognized card payment', message: 'I noticed a $129.99 payment to Northstar Supplies on October 6. I do not recognize this purchase. Please investigate and open a payment dispute.' },
  { id: 'REQ-1002', customerId: 'CUS-3072', name: 'Sam Rivera', transactionId: 'TXN-81002', amountCents: 4850, currency: 'USD', subject: 'Charged for a cancelled order', message: 'My $48.50 order from Harbor Books was cancelled, but the payment on October 7 still appears on my account. Please dispute this charge.' },
  { id: 'REQ-1003', customerId: 'CUS-4093', name: 'Jordan Lee', transactionId: 'TXN-99999', amountCents: 7500, currency: 'USD', subject: 'Payment reference not found', message: 'I would like to dispute a $75.00 payment with reference TXN-99999. Please check whether this transaction exists in your records.' },
];
export const transactions: Transaction[] = [
  { id: 'TXN-81001', customerId: 'CUS-2041', merchant: 'Northstar Supplies', amountCents: 12999, currency: 'USD', date: '2026-10-06', status: 'Settled' },
  { id: 'TXN-81002', customerId: 'CUS-3072', merchant: 'Harbor Books', amountCents: 4850, currency: 'USD', date: '2026-10-07', status: 'Settled' },
];
export function validateTransaction(request: Request, transaction: Transaction | undefined): { valid: boolean; message: string } {
  if (!transaction) return { valid: false, message: 'Transaction not found. No dispute can be created.' };
  if (request.transactionId !== transaction.id || request.customerId !== transaction.customerId || request.amountCents !== transaction.amountCents || request.currency !== transaction.currency) return { valid: false, message: 'Validation failed: transaction ID, customer ID, amount and currency must match the selected request.' };
  return { valid: true, message: 'Validation passed: transaction ID, customer ID, amount and currency match the request.' };
}
export function createDispute(request: Request, transaction: Transaction | undefined, verified: boolean, existing: Dispute[]): Dispute {
  const validation = validateTransaction(request, transaction);
  if (!validation.valid) throw new Error(validation.message);
  if (!verified) throw new Error('Confirm that you have reviewed the transaction before creating a dispute.');
  if (existing.some(item => item.requestId === request.id || item.transactionId === transaction!.id)) throw new Error('A dispute already exists for this transaction.');
  return { id: `DSP-${request.id.slice(4)}`, requestId: request.id, transactionId: transaction!.id, customerId: transaction!.customerId, amountCents: transaction!.amountCents, currency: transaction!.currency };
}
export const money = (cents: number, currency = 'USD') => new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(cents / 100);
