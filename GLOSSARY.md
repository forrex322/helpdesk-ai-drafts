# Support Drafts

A service that receives new support tickets from the Helpdesk, prepares an LLM-written Draft grounded in the Knowledge Base, lets an Operator moderate it, and delivers the approved Reply back through the Helpdesk.

## Language

### Inbound

**Helpdesk**:
The external ticketing system that owns the customer conversation. It pushes Events to us and accepts Replies from us.
_Avoid_: CRM, support system

**Event**:
One webhook notification from the Helpdesk about a new Ticket, identified by its `event_id`. The same Event may be delivered many times.
_Avoid_: Delivery, request, hook

**Ticket**:
A customer's support request (звернення) as we know it, created from exactly one Event. Carries the Helpdesk's ticket id, the customer's email, the message and the reply URL.
_Avoid_: Issue, case, request, appeal

**Customer**:
The person who wrote the Ticket and receives the Reply.
_Avoid_: Client, user

### Knowledge

**Knowledge Base**:
The set of Articles about the product that Drafts are grounded in.
_Avoid_: KB docs, FAQ, wiki

**Article**:
One short help page in the Knowledge Base, with a stable public link.
_Avoid_: Doc, page, entry

**Product**:
"Звітник" (Zvitnyk), the fictional reporting and dashboards SaaS that the Knowledge Base describes.

### Moderation

**Draft**:
The LLM-written answer to a Ticket, citing the Articles it relied on. It is a proposal only and is never sent as-is without an Operator's approval.
_Avoid_: Suggestion, answer, response

**Operator**:
A support agent who reviews Drafts in the web interface.
_Avoid_: Agent (ambiguous with AI agents), admin, moderator

**Approval**:
An Operator's decision to send a Draft, possibly after editing its text. The approved text becomes the Reply.
_Avoid_: Confirmation, accept

**Rejection**:
An Operator's decision that a Draft must not be sent. Final for that Ticket in this service.
_Avoid_: Decline, discard

### Outbound

**Reply**:
The approved text delivered to the Customer through the Helpdesk. Each Ticket has at most one Reply, and the Customer must receive it at most once.
_Avoid_: Response, answer, message

**Delivery**:
Handing a Reply to the Helpdesk until it acknowledges with `201 Created`. May take several attempts.
_Avoid_: Send, push

## Relationships

- An **Event** creates exactly one **Ticket**; repeated deliveries of the same Event create nothing new.
- A **Ticket** has at most one **Draft** and at most one **Reply**.
- A **Draft** cites zero or more **Articles**.
- An **Operator** turns a **Draft** into a **Reply** through **Approval**, or ends it through **Rejection**.

## Ticket lifecycle

`new → drafting → draft_ready → approved → sending → sent`, with the side exits `draft_failed` (drafting gave up), `rejected` (Operator said no) and `send_failed` (Delivery gave up). An Operator can retry from either failed state.
