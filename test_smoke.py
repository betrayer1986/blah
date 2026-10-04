from email.message import EmailMessage
import imap_to_nextcloud as m

ICS = b"""BEGIN:VCALENDAR\r\nVERSION:2.0\r\nMETHOD:REQUEST\r\nBEGIN:VEVENT\r\nUID:abc-1\r\nDTSTAMP:20261001T000000Z\r\nDTSTART:20261010T090000Z\r\nDTEND:20261010T100000Z\r\nSUMMARY:Test\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"""

class Fake:
    def __init__(self): self.calls = []
    def put(self, cal, uid, events): self.calls.append(("put", uid)); return 201
    def delete(self, uid): self.calls.append(("del", uid))

def mail(ics):
    msg = EmailMessage(); msg["Subject"] = "Einladung"; msg.set_content("hi")
    msg.add_attachment(ics, maintype="text", subtype="calendar", filename="i.ics")
    return msg.as_bytes()

def test_request_and_cancel():
    f = Fake()
    assert m.handle_message(mail(ICS), f) == 1
    assert m.handle_message(mail(ICS.replace(b"REQUEST", b"CANCEL")), f) == 1
    assert f.calls == [("put", "abc-1"), ("del", "abc-1")]
